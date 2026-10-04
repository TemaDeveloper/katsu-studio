import time
import json
import pytest
from fastapi.testclient import TestClient
from katsu.main import create_app
from katsu.models import StudioSettings
from katsu.config import WORKSPACE
from katsu.legacy import load
from helpers import FixtureOpenAI, FixtureVoice


class EmptyKeys:
    def status(self): return {'openai': False, 'elevenlabs': False}
    def get(self, provider): return None


def wait_done(c, id):
    deadline = time.monotonic()+30
    while time.monotonic() < deadline:
        p = c.get('/api/projects/'+id).json()
        if p['status'] not in ('queued', 'running'):
            return p
        time.sleep(.05)
    raise AssertionError('Worker did not finish')


def test_real_worker_to_download_and_missing_key_recovery(tmp_path):
    app = create_app(tmp_path, credentials=EmptyKeys(), providers=(FixtureOpenAI(), FixtureVoice()))
    app.state.store.save_settings(StudioSettings(voice_id='fixture', image_concurrency=1, remove_pauses=False))
    with TestClient(app) as c:
        p = c.post('/api/projects', json={'topic': 'Synthetic end-to-end test', 'target_seconds': 60}).json()
        done = wait_done(c, p['id'])
        assert done['status'] == 'completed', done['error']
        video = c.get(f"/api/projects/{p['id']}/artifacts/video?download=true")
        assert video.status_code == 200 and 'attachment' in video.headers['content-disposition']
        assert video.headers['content-type'] == 'video/mp4'
        assert c.get(f"/api/projects/{p['id']}/artifacts/verification").json()['full_decode']
    other = create_app(tmp_path / 'missing', credentials=EmptyKeys())
    with TestClient(other) as c:
        p = c.post('/api/projects', json={'topic': 'A real question'}).json()
        stopped = wait_done(c, p['id'])
        assert stopped['status'] == 'needs_attention'
        assert 'Settings' in stopped['error']
        assert stopped['estimated_committed_usd'] == 0


def test_fixed_existing_import_is_idempotent_and_preserves_originals(tmp_path):
    original = WORKSPACE / 'output/final_video.mp4'
    if not original.exists():
        pytest.skip('Owner-only historical import requires local output/ episode files.')
    before = load('compose_video').digest(original)
    with TestClient(create_app(tmp_path, worker_enabled=False, credentials=EmptyKeys())) as c:
        p = c.post('/api/import-existing').json()
        assert p['status'] == 'completed' and p['imported']
        assert p['actual_seconds'] > 560
        assert len(c.get(f"/api/projects/{p['id']}/scenes").json()) == 120
        assert c.post('/api/import-existing').json()['id'] == p['id']
        assert c.get(f"/api/projects/{p['id']}/artifacts/video", headers={'Range': 'bytes=0-99'}).status_code == 206
        assert 'manual' in p['artifacts']['words']['metadata']
    assert load('compose_video').digest(original) == before
