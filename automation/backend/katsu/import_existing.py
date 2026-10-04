import json
import shutil
from .models import ProjectCreate, StudioSettings, Script, Scene, Artifact, Source
from .store import atomic_json, fingerprint
from .legacy import load


def import_existing(store, workspace):
    manifest_path = workspace / 'output/PRODUCTION_MANIFEST.json'
    video = workspace / 'output/final_video.mp4'
    if not manifest_path.is_file() or not video.is_file():
        raise ValueError('The completed example is not available in this workspace.')
    manifest = json.loads(manifest_path.read_text())
    key = 'existing:' + load('compose_video').digest(video)
    # Keep the original submission body so a previously imported episode is idempotent.
    p = store.create_project(ProjectCreate(topic=manifest['title'], scene_count=120), StudioSettings(), key)
    if p.imported:
        return p
    root = store.project_dir(p.id)

    def copy(kind, source, relative, manual=True):
        dest = root / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        store.register_artifact(p.id, Artifact(kind=kind, path=relative, fingerprint=load('compose_video').digest(dest), metadata={'manual': manual, 'historical': True}))

    copy('video', video, 'existing/video.mp4')
    copy('audio', workspace / 'output/narration_no_pauses.mp3', 'existing/narration.mp3')
    copy('timeline', workspace / 'output/video_build/timeline.json', 'existing/timeline.json')
    copy('verification', workspace / 'output/video_build/quality_check/verification.json', 'existing/verification.json')
    copy('overlays', workspace / 'output/static_overlays.json', 'existing/overlays.json')
    transcript = json.loads((workspace / 'output/video_build/transcript_reviewed.json').read_text())
    words = transcript.get('words', transcript.get('transcription', {}).get('words'))
    if not words:
        raise ValueError('The existing narration timing is missing.')
    scenes, text, cursor = [], '', 0
    prompts = {x['shot']: x['prompt'] for x in json.loads((workspace / 'WHY_ARE_HUMANS_NEVER_SATISFIED_ALL_IMAGE_PROMPTS.json').read_text())}
    for shot in manifest['shots']:
        voiceover = shot['voiceover'] + '\n\n'
        scenes.append(Scene(id=shot['shot'], narration_start=cursor, narration_end=cursor+len(voiceover), voiceover=voiceover, visual=shot['visual'], prompt=prompts[shot['shot']]))
        cursor += len(voiceover)
        text += voiceover
        # Only fixed manifest assets may be imported; never arbitrary client paths.
        source = workspace / 'output/images' / f"shot-{shot['shot']:03}.png"
        copy(f"scene_{shot['shot']}", source, f"existing/images/{shot['shot']}.png")
    script = Script(title=manifest['title'], narration=text, sources=[], claims=[])
    for kind, data in (('script', script.model_dump()), ('scenes', [x.model_dump() for x in scenes]), ('words', words), ('sources', [])):
        file = root / 'existing' / (kind+'.json')
        atomic_json(file, data)
        store.register_artifact(p.id, Artifact(kind=kind, path=str(file.relative_to(root)), fingerprint=fingerprint(data), metadata={'manual': True, 'historical': True}))
    return store.update_project(p.id, imported=True, scene_planning='legacy', status='completed', stage='complete',
        total_assets=len(scenes), completed_assets=len(scenes), settings=p.settings.model_copy(update={'scene_count': len(scenes)}),
        actual_seconds=manifest.get('actual_audio_seconds', 568.273084), title=manifest['title'])
