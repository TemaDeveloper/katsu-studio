from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4
import json
from .models import Artifact, Script, Scene, TimedWord, Source, ThumbnailPlan
from .store import atomic_json, fingerprint
from .budget import Budget
from .providers.errors import ProviderError, UnknownOutcome
from .providers.openai import OpenAIProvider
from .providers.elevenlabs import ElevenLabsProvider
from .config import channel_profile
from .content import validate_scene_spans
from .timing import chunk_narration
from .audio import prepare_narration, duration
from .rendering import render_video
from .legacy import load
from .thumbnail import render_thumbnail, thumbnail_key


class Cancelled(Exception):
    pass


class Pipeline:
    def __init__(self, store, keys=None, providers=None):
        self.store, self.keys, self.providers = store, keys, providers
        self.budget = Budget(store)

    def cancel(self, id):
        self.store.update_project(id, cancel_requested=True)

    def checkpoint(self, id, stage):
        if self.store.get_project(id).cancel_requested:
            raise Cancelled()
        self.store.update_project(id, status='running', stage=stage)

    def valid(self, id, kind, key):
        artifact = self.store.get_project(id).artifacts.get(kind)
        if artifact and (artifact.fingerprint == key or artifact.metadata.get('manual')):
            try:
                return self.store.artifact_path(id, kind)
            except KeyError:
                pass
        return self.store.find_artifact(id, kind, key)

    def save(self, id, kind, data, key, metadata=None):
        project_dir = self.store.project_dir(id)
        file = project_dir / 'assets' / f'{kind}-{key}.json'
        atomic_json(file, data)
        self.store.register_artifact(id, Artifact(kind=kind, path=str(file.relative_to(project_dir)), fingerprint=key, metadata=metadata or {}))
        return file

    def paid(self, id, kind, key, estimate, operation):
        request_key = id + ':' + kind + ':' + key
        self.checkpoint(id, self.store.get_project(id).stage)
        saved = self.budget.saved_result(request_key)
        if saved:
            types = {'Source': Source, 'Script': Script, 'Scene': Scene, 'Artifact': Artifact, 'ThumbnailPlan': ThumbnailPlan}
            if saved['type'] == 'dict':
                return saved['value']
            if saved['type'].endswith('[]'):
                return [types[saved['type'][:-2]].model_validate(x) for x in saved['value']]
            return types[saved['type']].model_validate(saved['value'])
        if not self.providers:
            provider = 'elevenlabs' if kind.startswith('voice_chunk') else 'openai'
            if not self.keys.get(provider) or (provider == 'elevenlabs' and not self.store.get_project(id).settings.voice_id):
                if kind.startswith('thumbnail'):
                    raise ValueError('Add your OpenAI API key in Settings, then continue thumbnail production. Your video is saved.')
                raise ValueError('Open Settings, add your OpenAI and ElevenLabs keys, and choose a voice. Then resume this project.')
        self.budget.reserve(id, request_key, estimate)
        try:
            value = operation()
        except UnknownOutcome:
            self.budget.mark_unknown(request_key)
            raise
        except ProviderError as exc:
            # Only a definite rejection releases the estimate. Invalid paid output needs inspection.
            if 'rejected the request (HTTP' in str(exc):
                self.budget.settle(request_key, {'failed': True})
            else:
                self.budget.mark_unknown(request_key)
            raise
        except Exception:
            self.budget.mark_unknown(request_key)
            raise
        provider = self._current_providers[1 if kind.startswith('voice_chunk') else 0]
        if isinstance(value, list):
            result = {'type': type(value[0]).__name__ + '[]', 'value': [x.model_dump() for x in value]}
        elif isinstance(value, dict):
            result = {'type': 'dict', 'value': value}
        else:
            result = {'type': type(value).__name__, 'value': value.model_dump()}
        # The response and settlement are one durable transaction. Registration can be reconciled on resume.
        self.budget.settle(request_key, {'returned': True, 'result': result, **getattr(provider, 'last_metadata', {})})
        return value

    def run(self, id):
        s = self.store
        p = s.get_project(id)
        root = s.project_dir(id)
        automatic_scenes = p.scene_planning == 'automatic'
        settings = p.settings.model_copy(update={'scene_count': None}) if automatic_scenes else p.settings
        try:
            if p.render_only:
                from .artwork import render_saved
                render_saved(self, id)
                return
            if p.artwork_edit:
                from .artwork import run_edit
                job = p.artwork_edit
                edit_settings = settings.model_copy(update={'image_model': job.image_model, 'image_quality': job.image_quality})
                saved = self.budget.saved_result(id + ':artwork_edit_' + job.kind + ':' + job.request_key)
                key = self.keys.get('openai') if self.keys else None
                if not saved and not self.providers and not key:
                    raise ValueError('Add your OpenAI API key in Settings, then continue the saved image edit.')
                ai = self.providers[0] if self.providers else OpenAIProvider(key, edit_settings) if key else None
                self._current_providers = (ai, None)
                run_edit(self, id, ai)
                return
            if self.providers:
                ai, voice = self.providers
            else:
                openai_key, voice_key = self.keys.get('openai'), self.keys.get('elevenlabs')
                if not p.imported and 'audio' not in p.artifacts and (not openai_key or not voice_key or not settings.voice_id):
                    raise ValueError('Open Settings, add your OpenAI and ElevenLabs keys, and choose a voice. Then resume this project.')
                ai = OpenAIProvider(openai_key, settings) if openai_key else None
                voice = ElevenLabsProvider(voice_key, settings) if voice_key else None
            self._current_providers = (ai, voice)
            s.update_project(id, error=None)
            if p.thumbnail_only:
                script = Script.model_validate_json(s.artifact_path(id, 'script').read_text())
                style = channel_profile(s.root)
                reference = s.root / 'channel/reference.png'
                if not reference.is_file():
                    raise ValueError('The saved Katsu character reference is missing.')
                style_hash = fingerprint([style, load('compose_video').digest(reference)])
                self.finish_thumbnail(id, script, style, style_hash, reference, ai)
                self.checkpoint(id, 'complete')
                s.update_project(id, status='completed', stage='complete', thumbnail_only=False, error=None)
                return
            self.checkpoint(id, 'research')
            research_key = fingerprint([p.topic, settings.text_model, 'research-v1'])
            path = self.valid(id, 'sources', research_key)
            if not path:
                s.remove_artifacts(id, ('video', 'timeline', 'verification'))
                sources = self.paid(id, 'research', research_key, settings.text_request_estimate_usd, lambda: ai.research(p.topic))
                path = self.save(id, 'sources', [v.model_dump() for v in sources], research_key, getattr(ai, 'last_metadata', {}))
            sources = [Source.model_validate(x) for x in json.loads(path.read_text())]
            self.checkpoint(id, 'writing')
            script_inputs = [research_key, [v.model_dump() for v in sources], settings.text_model, settings.target_seconds, settings.words_per_minute]
            script_key = fingerprint(script_inputs + (['script-auto-v1'] if automatic_scenes else [settings.scene_count, 'script-v1']))
            path = self.valid(id, 'script', script_key)
            if not path:
                s.remove_artifacts(id, ('video', 'timeline', 'verification'))
                script = self.paid(id, 'writing', script_key, settings.text_request_estimate_usd, lambda: ai.write_script(p.topic, sources, round(settings.target_seconds/60*settings.words_per_minute)))
                path = self.save(id, 'script', script.model_dump(), script_key, getattr(ai, 'last_metadata', {}))
            script = Script.model_validate_json(path.read_text())
            s.update_project(id, title=script.title)
            self.checkpoint(id, 'planning')
            style = channel_profile(s.root)
            reference = s.root / 'channel/reference.png'
            if not reference.is_file():
                raise ValueError('The saved Katsu character reference is missing.')
            style_hash = fingerprint([style, load('compose_video').digest(reference)])
            scenes_key = fingerprint([script.model_dump(), style_hash, settings.text_model, 'scenes-auto-v1'] if automatic_scenes else [script.model_dump(), style_hash, settings.scene_count, settings.text_model, 'scenes-v1'])
            path = self.valid(id, 'scenes', scenes_key)
            if not path:
                s.remove_artifacts(id, ('video', 'timeline', 'verification'))
                scenes = self.paid(id, 'planning', scenes_key, settings.text_request_estimate_usd, lambda: ai.plan_scenes(script, settings.scene_count, style))
                path = self.save(id, 'scenes', [v.model_dump() for v in scenes], scenes_key, getattr(ai, 'last_metadata', {}))
            scenes = [Scene.model_validate(v) for v in json.loads(path.read_text())]
            validate_scene_spans(script, scenes)
            s.update_project(id, total_assets=len(scenes))
            self.checkpoint(id, 'images')
            jobs = []
            for scene in scenes:
                key = fingerprint([scene.prompt, scene.visual, style_hash, settings.image_model, settings.image_quality, 'image-v1'])
                if not self.valid(id, f'scene_{scene.id}', key):
                    jobs.append((scene, key))
            s.update_project(id, completed_assets=len(scenes)-len(jobs))
            if jobs:
                s.remove_artifacts(id, ('video', 'timeline', 'verification'))

            def image_job(scene, key):
                image_scene = scene.model_copy(update={'prompt': style['style'] + '\nPreserve the reference character’s design, and draw a NEW scene: ' + scene.prompt + '\nVisual: ' + scene.visual})
                dest = root / 'images' / f'{scene.id}-{key}.png'
                artifact = self.paid(id, f'image_{scene.id}', key, settings.image_estimate_usd, lambda: ai.generate_image(image_scene, reference, dest))
                artifact.path = str(dest.relative_to(root))
                artifact.fingerprint = key
                s.register_artifact(id, artifact)

            # Dispatch bounded batches; cancelling never queues further paid work.
            for start in range(0, len(jobs), settings.image_concurrency):
                self.checkpoint(id, 'images')
                batch = jobs[start:start+settings.image_concurrency]
                with ThreadPoolExecutor(max_workers=settings.image_concurrency) as pool:
                    futures = [pool.submit(image_job, *job) for job in batch]
                    failure = None
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as exc:
                            failure = failure or exc
                        s.update_project(id, completed_assets=sum(f'scene_{x.id}' in s.get_project(id).artifacts for x in scenes))
                    if failure:
                        raise failure
            self.checkpoint(id, 'narration')
            narration_key = fingerprint([script.narration, settings.voice_id, settings.voice_model, settings.voice_stability, settings.voice_similarity, settings.voice_speed, 'voice-v1'])
            pause_settings = {k: v for k, v in settings.model_dump().items() if k in ('remove_pauses', 'pause_threshold_db', 'minimum_pause_seconds', 'retained_pause_seconds')}
            audio_key = fingerprint([narration_key, pause_settings, 'audio-v1'])
            audio, words_path = self.valid(id, 'audio', audio_key), self.valid(id, 'words', audio_key)
            if not audio or not words_path:
                s.remove_artifacts(id, ('audio', 'words', 'video', 'timeline', 'verification'))
            chunks = []
            for index, (a, b) in enumerate([] if audio and words_path else chunk_narration(script.narration)):
                text = script.narration[a:b]
                key = fingerprint([narration_key, a, b])
                kind = f'voice_chunk_{index}'
                path = self.valid(id, kind, key)
                if not path:
                    dest = root / 'voice' / f'{index}-{key}.mp3'
                    value = self.paid(id, kind, key, max(.01, len(text)/1000*settings.voice_per_1000_chars_usd), lambda: voice.generate_speech(text, dest, script.narration[max(0, a-1000):a], script.narration[b:b+1000]))
                    value['path'] = str(dest.relative_to(root))
                    path = self.save(id, kind, value, key, getattr(voice, 'last_metadata', {}))
                chunk = json.loads(path.read_text())
                chunk['path'] = str(s.contained(id, chunk['path']))
                chunks.append(chunk)
            self.checkpoint(id, 'timing')
            if not audio or not words_path:
                audio_dir = root / 'audio' / audio_key
                audio_dir.mkdir(parents=True, exist_ok=True)
                audio, words = prepare_narration(audio_dir, chunks, pause_settings)
                s.register_artifact(id, Artifact(kind='audio', path=str(audio.relative_to(root)), fingerprint=audio_key))
                words_path = self.save(id, 'words', [w.model_dump() for w in words], audio_key)
            words = [TimedWord.model_validate(x) for x in json.loads(words_path.read_text())]
            s.update_project(id, actual_seconds=duration(audio))
            self.checkpoint(id, 'rendering')
            images = {scene.id: s.artifact_path(id, f'scene_{scene.id}') for scene in scenes}
            export_key = fingerprint([audio_key, [load('compose_video').digest(p) for p in images.values()], [x.model_dump() for x in scenes], [x.model_dump() for x in words], 'render-v1'])
            if not self.valid(id, 'video', export_key):
                overlay_config = {}
                if p.imported and 'overlays' in s.get_project(id).artifacts:
                    overlay_config = json.loads(s.artifact_path(id, 'overlays').read_text())
                artifact = render_video(root, scenes, words, audio, images, overlay_config)
                artifact.fingerprint = export_key
                s.register_artifact(id, artifact)
                for kind in ('timeline', 'verification'):
                    s.register_artifact(id, Artifact(kind=kind, path=artifact.metadata[kind+'_path'], fingerprint=export_key))
            s.update_project(id, thumbnail_only=True)
            self.finish_thumbnail(id, script, style, style_hash, reference, ai)
            self.checkpoint(id, 'complete')
            s.update_project(id, status='completed', stage='complete', thumbnail_only=False, error=None)
        except Cancelled:
            s.update_project(id, status='cancelled', error=None)
        except (ValueError, OSError) as exc:
            s.update_project(id, status='needs_attention', error=str(exc))
        except Exception:
            s.update_project(id, status='needs_attention', error='Production stopped unexpectedly. Your saved work is preserved. Check local processing tools and resume.')

    def finish_thumbnail(self, id, script, style, style_hash, reference, ai):
        s = self.store
        p = s.get_project(id)
        root, settings = s.project_dir(id), p.settings
        self.checkpoint(id, 'thumbnail')
        # A historical or owner-supplied thumbnail remains usable until explicitly replaced.
        existing = p.artifacts.get('thumbnail')
        if existing and existing.metadata.get('manual'):
            try:
                s.artifact_path(id, 'thumbnail')
                return
            except KeyError:
                pass
        plan_key = fingerprint([script.title, script.narration, style_hash, settings.text_model, p.thumbnail_revision, 'thumbnail-plan-v1'])
        path = self.valid(id, 'thumbnail_plan', plan_key)
        if not path:
            s.remove_artifacts(id, ('thumbnail', 'thumbnail_artwork'))
            plan = self.paid(id, 'thumbnail_plan', plan_key, settings.text_request_estimate_usd, lambda: ai.plan_thumbnail(script, style))
            path = self.save(id, 'thumbnail_plan', plan.model_dump(), plan_key, getattr(ai, 'last_metadata', {}))
        plan = ThumbnailPlan.model_validate_json(path.read_text())
        art_key = fingerprint([plan.model_dump(), plan_key, style_hash, settings.image_model, settings.image_quality, 'thumbnail-art-v1'])
        artwork = self.valid(id, 'thumbnail_artwork', art_key)
        if not artwork:
            s.remove_artifacts(id, ('thumbnail',))
            scene = Scene(id=0, narration_start=0, narration_end=0, voiceover='', visual=plan.visual,
                prompt=style['style']+'\nCreate a NEW thumbnail illustration: '+plan.prompt+'\nVisual: '+plan.visual+'\nKeep all figures and props on the RIGHT half, with the LEFT half blank white for text. No lettering. Keep important figures in the central 80% vertically.')
            dest = root / 'thumbnails' / f'art-{art_key}.png'
            artifact = self.paid(id, 'thumbnail_image', art_key, settings.image_estimate_usd, lambda: ai.generate_image(scene, reference, dest))
            artifact.kind, artifact.path, artifact.fingerprint = 'thumbnail_artwork', str(dest.relative_to(root)), art_key
            s.register_artifact(id, artifact)
            artwork = dest
        final_key = thumbnail_key(plan.headline, artwork)
        if not self.valid(id, 'thumbnail', final_key):
            self.checkpoint(id, 'thumbnail')
            dest = root / 'thumbnails' / f'{final_key}.jpg'
            metadata = render_thumbnail(artwork, plan.headline, dest)
            s.register_artifact(id, Artifact(kind='thumbnail', path=str(dest.relative_to(root)), fingerprint=final_key,
                metadata={**metadata, 'source': 'ai_artwork', 'plan_fingerprint': plan_key}))
