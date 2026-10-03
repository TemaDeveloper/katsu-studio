import json
import re
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from fastapi.responses import FileResponse
from .models import Scene, SceneEdit, Script
from .pipeline import Pipeline
from .store import fingerprint
from .config import WORKSPACE, AUTOMATION
from .providers.openai import OpenAIProvider
from .providers.elevenlabs import ElevenLabsProvider
from .providers.errors import ProviderError
from .import_existing import import_existing


def attach_routes(app, store, keys):
    def idle(id):
        p = store.get_project(id)
        if p.status == 'running' or (app.state.worker and app.state.worker.busy(id)):
            raise ValueError('Wait for production to stop before editing or resuming.')
        return p

    def queue(id, thumbnail_only=False):
        store.update_project(id, status='queued', error=None, cancel_requested=False, thumbnail_only=thumbnail_only)
        if app.state.worker:
            app.state.worker.enqueue(id)
        return store.get_project(id)

    def thumbnail_settings(project):
        current = store.settings()
        fields = ('text_model', 'image_model', 'image_quality', 'text_request_estimate_usd', 'image_estimate_usd', 'budget_usd')
        return project.settings.model_copy(update={k: getattr(current, k) for k in fields})

    @app.post('/api/connections/check')
    def check():
        settings = store.settings()
        results = {}
        for name in ('openai', 'elevenlabs'):
            key = keys.get(name)
            if not key:
                results[name] = {'ok': False, 'message': 'Add your API key.'}
                continue
            try:
                if name == 'openai':
                    results[name] = OpenAIProvider(key, settings).check()
                else:
                    voices = ElevenLabsProvider(key, settings).list_voices()
                    selected = any(v['id'] == settings.voice_id for v in voices)
                    results[name] = {'ok': selected, 'message': 'Connected. Selected voice is accessible.' if selected else 'Connected. Choose an accessible voice below.'}
            except (ProviderError, ValueError) as exc:
                results[name] = {'ok': False, 'message': str(exc)}
        return results

    @app.get('/api/voices')
    def voices():
        key = keys.get('elevenlabs')
        if not key:
            raise ValueError('Add your ElevenLabs API key first.')
        return ElevenLabsProvider(key, store.settings()).list_voices()

    @app.post('/api/import-existing')
    def import_example():
        with store.lock:
            return import_existing(store, WORKSPACE)

    @app.post('/api/projects/{id}/cancel')
    def cancel(id: str):
        Pipeline(store, keys).cancel(id)
        if store.get_project(id).status == 'queued':
            store.update_project(id, status='cancelled')
        return store.get_project(id)

    @app.post('/api/projects/{id}/resume')
    def resume(id: str, apply_settings: bool = False):
        p = idle(id)
        if apply_settings:
            settings = thumbnail_settings(p) if p.thumbnail_only else store.settings()
            settings.target_seconds, settings.scene_count = p.settings.target_seconds, p.settings.scene_count
            store.update_project(id, settings=settings)
        return queue(id, thumbnail_only=p.thumbnail_only)

    @app.post('/api/projects/{id}/render')
    def render(id: str):
        idle(id)
        if 'scenes' not in store.get_project(id).artifacts:
            raise ValueError('Create the script and images before exporting.')
        store.remove_artifacts(id, ('video', 'verification', 'timeline'))
        return queue(id)

    @app.post('/api/projects/{id}/thumbnail')
    def thumbnail(id: str, regenerate: bool = False):
        p = idle(id)
        if 'video' not in p.artifacts:
            raise ValueError('Finish the video before creating its thumbnail.')
        if regenerate:
            store.update_project(id, thumbnail_revision=uuid4().hex)
            store.remove_artifacts(id, ('thumbnail', 'thumbnail_plan', 'thumbnail_artwork'))
        store.update_project(id, settings=thumbnail_settings(p))
        return queue(id, thumbnail_only=True)

    @app.get('/api/projects/{id}/scenes')
    def scenes(id: str):
        store.get_project(id)
        try:
            return json.loads(store.artifact_path(id, 'scenes').read_text())
        except KeyError:
            return []

    @app.patch('/api/projects/{id}/scenes/{scene_id}')
    def edit(id: str, scene_id: int, value: SceneEdit):
        p = idle(id)
        rows = [Scene.model_validate(x) for x in scenes(id)]
        target = next((x for x in rows if x.id == scene_id), None)
        if not target:
            raise KeyError('Scene not found.')
        service = Pipeline(store, keys)
        script = Script.model_validate_json(store.artifact_path(id, 'script').read_text())
        # An owner-edited plan and its canonical wording are one content revision.
        service.save(id, 'script', script.model_dump(), fingerprint(script.model_dump()), {'manual': True, 'owner_edited': True})
        if value.voiceover is not None and value.voiceover != target.voiceover:
            target.voiceover = value.voiceover
            script = Script.model_validate_json(store.artifact_path(id, 'script').read_text())
            script.narration = ''.join(x.voiceover for x in rows)
            cursor = 0
            for row in rows:
                row.narration_start, row.narration_end = cursor, cursor+len(row.voiceover)
                cursor = row.narration_end
            service.save(id, 'script', script.model_dump(), fingerprint(script.model_dump()), {'manual': True, 'owner_edited': True})
            store.remove_artifacts(id, ['audio', 'words', 'video', 'timeline', 'verification', 'thumbnail', 'thumbnail_plan', 'thumbnail_artwork'] + [k for k in p.artifacts if k.startswith('voice_chunk_')])
            store.update_project(id, actual_seconds=None)
        if value.visual is not None and value.visual != target.visual:
            target.visual = value.visual
            target.prompt = value.visual
            store.remove_artifacts(id, [f'scene_{scene_id}', 'video', 'timeline', 'verification'])
        service.save(id, 'scenes', [r.model_dump() for r in rows], fingerprint([r.model_dump() for r in rows]), {'manual': True})
        store.update_project(id, status='needs_attention', thumbnail_only=False, error='Changes saved. Continue production to update the video.')
        return rows

    @app.post('/api/projects/{id}/scenes/{scene_id}/regenerate')
    def regenerate(id: str, scene_id: int):
        idle(id)
        if not any(x['id'] == scene_id for x in scenes(id)):
            raise KeyError('Scene not found.')
        artifact = store.get_project(id).artifacts.get(f'scene_{scene_id}')
        # Same prompt must get a new request identity after explicit regeneration.
        rows = [Scene.model_validate(x) for x in scenes(id)]
        target = next(x for x in rows if x.id == scene_id)
        script = Script.model_validate_json(store.artifact_path(id, 'script').read_text())
        Pipeline(store, keys).save(id, 'script', script.model_dump(), fingerprint(script.model_dump()), {'manual': True, 'owner_edited': True})
        target.prompt += '\nNew variation request: ' + uuid4().hex[:8]
        Pipeline(store, keys).save(id, 'scenes', [x.model_dump() for x in rows], fingerprint([x.model_dump() for x in rows]), {'manual': True})
        store.remove_artifacts(id, [f'scene_{scene_id}', 'video', 'timeline', 'verification'])
        return queue(id)

    @app.post('/api/projects/{id}/package-images')
    def package_images(id: str):
        idle(id)
        from .downloads import prepare_downloads
        prepare_downloads(store, id)
        return store.get_project(id)

    @app.post('/api/projects/{id}/acknowledge-unknown')
    def acknowledge(id: str):
        idle(id)
        with store.lock:
            rows = store.db.execute("SELECT key FROM requests WHERE project_id=? AND state='unknown'", (id,)).fetchall()
            for row in rows:
                store.db.execute("UPDATE requests SET key=?,state='acknowledged' WHERE key=?", (row[0]+':acknowledged:'+uuid4().hex, row[0]))
            store.db.commit()
        return {'acknowledged': len(rows), 'message': 'Prior estimates remain counted. The next attempt may incur another charge.'}

    @app.get('/api/projects/{id}/requests')
    def requests(id: str):
        store.get_project(id)
        with store.lock:
            rows = store.db.execute('SELECT key,estimate,state,usage FROM requests WHERE project_id=?', (id,)).fetchall()
        return [{'key': r[0], 'estimated_usd': r[1], 'state': r[2], 'metadata': {k: v for k, v in json.loads(r[3]).items() if k != 'result'}} for r in rows]

    @app.get('/{path:path}', include_in_schema=False)
    def frontend(path: str):
        if path.startswith('api/'):
            raise HTTPException(404, 'Route not found.')
        root = AUTOMATION / 'frontend/dist'
        candidate = (root / path).resolve()
        if candidate.is_relative_to(root.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        if (path in ('', 'new', 'settings') or re.fullmatch(r'projects/[0-9a-f-]{36}', path)) and (root / 'index.html').is_file():
            return FileResponse(root / 'index.html')
        raise HTTPException(404, 'Page not found.')
