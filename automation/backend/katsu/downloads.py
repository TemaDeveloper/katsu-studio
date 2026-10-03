import json
import zipfile
from .models import Artifact
from .store import fingerprint
from .legacy import load


def prepare_downloads(store, id):
    project = store.get_project(id)
    root = store.project_dir(id)
    scenes = json.loads(store.artifact_path(id, 'scenes').read_text())
    script = json.loads(store.artifact_path(id, 'script').read_text())
    images = [(s, store.artifact_path(id, f"scene_{s['id']}")) for s in scenes]
    key = fingerprint([script, scenes, [load('compose_video').digest(p) for _, p in images]])
    folder = root / 'downloads'
    folder.mkdir(exist_ok=True)
    text = folder / f'narration-{key}.txt'
    text.write_text(script['narration'])
    store.register_artifact(id, Artifact(kind='narration_text', path=str(text.relative_to(root)), fingerprint=key))
    bundle = folder / f'images-{key}.zip'
    if not bundle.exists():
        temporary = bundle.with_suffix('.part.zip')
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED) as zip_file:
            for s, image in images:
                zip_file.write(image, f"scene-{s['id']:03}.png")
            zip_file.writestr('scenes.json', json.dumps(scenes, indent=2, ensure_ascii=False))
        temporary.replace(bundle)
    store.register_artifact(id, Artifact(kind='images_package', path=str(bundle.relative_to(root)), fingerprint=key))
