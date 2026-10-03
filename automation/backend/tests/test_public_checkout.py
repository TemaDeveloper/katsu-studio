from fastapi.testclient import TestClient
from PIL import Image
from katsu import config
from katsu.main import create_app


def test_new_checkout_starts_with_branding_without_original_episode(tmp_path, monkeypatch):
    # A public checkout has no owner's output/ or saved channel data.
    monkeypatch.setattr(config, 'WORKSPACE', tmp_path / 'empty-checkout')
    data = tmp_path / 'new-data'
    with TestClient(create_app(data, worker_enabled=False)) as client:
        avatar = client.get('/api/brand/avatar')
        assert avatar.status_code == 200, 'A new checkout must include the channel avatar'
        assert avatar.headers['content-type'] == 'image/png'
        assert client.get('/api/projects').json() == []
    with Image.open(data / 'channel/reference.png') as reference:
        reference.verify()
