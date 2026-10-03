import json
from fastapi.testclient import TestClient
from katsu.store import Store
from katsu.models import ProjectCreate, StudioSettings
from katsu.pipeline import Pipeline
from katsu.main import create_app
from helpers import FixtureOpenAI, FixtureVoice


def make(tmp_path, **kwargs):
    store = Store(tmp_path)
    p = store.create_project(ProjectCreate(topic='Synthetic pipeline test', scene_count=4), StudioSettings(voice_id='fixture', remove_pauses=False, image_concurrency=1), 'one')
    from katsu.config import channel_profile
    channel_profile(store.root)
    ai, voice = FixtureOpenAI(**kwargs), FixtureVoice()
    return store, p, Pipeline(store, providers=(ai, voice)), ai, voice


def test_full_pipeline_and_repeat_resume_reuse_successful_paid_assets(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    pipeline.run(p.id)
    done = store.get_project(p.id)
    assert done.status == 'completed', done.error
    assert done.actual_seconds == 2
    assert store.artifact_path(p.id, 'video').stat().st_size > 1000
    assert json.loads(store.artifact_path(p.id, 'verification').read_text())['full_decode'] is True
    pipeline.run(p.id)
    assert ai.images == 4
    assert voice.calls == 1


def test_editing_wording_invalidates_audio_but_image_edits_preserve_it(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    pipeline.run(p.id)
    c = TestClient(create_app(tmp_path, worker_enabled=False))
    url = f'/api/projects/{p.id}/scenes/1'
    assert c.patch(url, json={'visual': 'A red gift'}).status_code == 200
    state = store.get_project(p.id)
    assert 'audio' in state.artifacts and 'video' not in state.artifacts and 'scene_1' not in state.artifacts
    assert c.patch(url, json={'voiceover': 'A new gift.\n\n'}).status_code == 200
    state = store.get_project(p.id)
    assert 'audio' not in state.artifacts and 'words' not in state.artifacts
    scenes = c.get(f'/api/projects/{p.id}/scenes').json()
    assert scenes[0]['voiceover'] == 'A new gift.\n\n'
    assert scenes[1]['narration_start'] == 13
    pipeline.run(p.id)
    assert store.get_project(p.id).status == 'completed'
    assert voice.calls == 2 and ai.images == 5


def test_cancellation_stops_new_calls_and_keeps_inflight_image(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    ai.on_image = lambda: pipeline.cancel(p.id)
    pipeline.run(p.id)
    assert store.get_project(p.id).status == 'cancelled'
    assert ai.images == 1 and voice.calls == 0
    assert 'scene_1' in store.get_project(p.id).artifacts
