from pathlib import Path
from fastapi.testclient import TestClient
from katsu.main import create_app


def client(tmp_path):
    return TestClient(create_app(tmp_path, worker_enabled=False))


def test_creation_is_persisted_and_double_submit_is_idempotent(tmp_path):
    c = client(tmp_path)
    payload = {"topic": "Why are humans never satisfied?"}
    first = c.post('/api/projects', json=payload, headers={'Idempotency-Key': 'same-click'})
    assert first.status_code == 201
    second = c.post('/api/projects', json=payload, headers={'Idempotency-Key': 'same-click'})
    assert second.json()['id'] == first.json()['id']
    reopened = client(tmp_path)
    assert len(reopened.get('/api/projects').json()) == 1
    assert first.json()['settings']['target_seconds'] == 480
    assert first.json()['settings']['scene_count'] is None
    assert first.json()['total_assets'] == 0
    assert c.post('/api/projects', json={'topic': 'Other topic'}, headers={'Idempotency-Key': 'same-click'}).status_code == 409


def test_validation_and_private_configuration(tmp_path):
    c = client(tmp_path)
    for payload in ({'topic': 'x'}, {'topic': '  '}, {'topic': 'A topic', 'scene_count': 121}, {'topic': 'A topic', 'budget_usd': -1}):
        assert c.post('/api/projects', json=payload).status_code == 422
    assert c.get('/api/settings').json()['connections'] == {'openai': False, 'elevenlabs': False}
    assert c.post('/api/projects', json={'topic': 'A topic'}, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert c.get('/api/projects/not-a-uuid').status_code == 404
    settings = c.get('/api/settings').json()['settings']
    settings['scene_count'] = 24
    assert c.put('/api/settings', json=settings).status_code == 200
    assert client(tmp_path).get('/api/settings').json()['settings']['scene_count'] == 24
    assert 'api_key' not in c.get('/api/settings').text


def test_unregistered_download_cannot_read_arbitrary_files(tmp_path):
    c = client(tmp_path)
    p = c.post('/api/projects', json={'topic': 'A topic'}).json()
    assert c.get(f"/api/projects/{p['id']}/artifacts/secret").status_code == 404
    assert c.get('/api/projects/../../etc/passwd').status_code in (404, 400)
