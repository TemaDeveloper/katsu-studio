import json
import zipfile
from fastapi.testclient import TestClient
from test_pipeline import make
from helpers import FixtureOpenAI
from katsu.pipeline import Pipeline
from katsu.models import Script
from katsu.main import create_app


def test_paid_result_survives_failure_before_artifact_registration(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    calls = []
    research = ai.research
    ai.research = lambda topic: (calls.append(topic), research(topic))[1]
    original = pipeline.save
    def disk_failure(*args, **kwargs):
        raise OSError('Fixture disk interruption')
    pipeline.save = disk_failure
    pipeline.run(p.id)
    assert store.get_project(p.id).status == 'needs_attention'
    pipeline.save = original
    pipeline.run(p.id)
    assert store.get_project(p.id).status == 'completed', store.get_project(p.id).error
    assert len(calls) == 1


def test_restoring_model_settings_recovers_saved_image_versions_without_paying_again(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    pipeline.run(p.id)
    original = store.get_project(p.id).settings
    changed = original.model_copy(update={'image_model': 'model-B'})
    store.update_project(p.id, settings=changed)
    pipeline.run(p.id)
    store.update_project(p.id, settings=original)
    pipeline.run(p.id)
    assert store.get_project(p.id).status == 'completed', store.get_project(p.id).error
    assert ai.images == 8 and voice.calls == 1


def test_owner_visual_edit_and_canonical_script_stay_together_after_writing_settings_change(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    pipeline.run(p.id)
    c = TestClient(create_app(tmp_path, worker_enabled=False))
    c.patch(f'/api/projects/{p.id}/scenes/1', json={'visual': 'Owner-selected gift'})
    settings = store.get_project(p.id).settings
    settings.text_model = 'new-writer'
    store.update_project(p.id, settings=settings)
    def forbidden_rewrite(*args):
        raise AssertionError('Owner-edited episode must keep its canonical script')
    ai.write_script = forbidden_rewrite
    pipeline.run(p.id)
    assert store.get_project(p.id).status == 'completed', store.get_project(p.id).error
    assert c.get(f'/api/projects/{p.id}/scenes').json()[0]['visual'] == 'Owner-selected gift'
    assert voice.calls == 1


def test_download_package_contains_only_registered_images_and_matching_wording(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    pipeline.run(p.id)
    c = TestClient(create_app(tmp_path, worker_enabled=False))
    r = c.post(f'/api/projects/{p.id}/package-images')
    assert r.status_code == 200
    with zipfile.ZipFile(store.artifact_path(p.id, 'images_package')) as z:
        assert z.namelist() == ['scene-001.png','scene-002.png','scene-003.png','scene-004.png','scenes.json']
        rows = json.loads(z.read('scenes.json'))
        assert rows[0]['voiceover'] == 'One gift.\n\n'
    text = c.get(f'/api/projects/{p.id}/artifacts/narration_text?download=true')
    assert text.status_code == 200 and text.text.startswith('One gift.')
