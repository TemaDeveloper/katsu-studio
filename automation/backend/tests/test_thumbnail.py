import json
import httpx
import pytest
from openai import OpenAI
from PIL import Image
from fastapi.testclient import TestClient
from katsu.main import create_app
from katsu.pipeline import Pipeline
from katsu.providers.errors import UnknownOutcome
from katsu.providers.errors import ProviderError
from katsu.providers.openai import OpenAIProvider
from katsu.models import StudioSettings
from test_pipeline import make


def test_automatic_export_finishes_with_downloadable_thumbnail(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    pipeline.run(p.id)
    done = store.get_project(p.id)
    assert done.status == 'completed', done.error
    assert 'thumbnail' in done.artifacts, 'A finished episode must include its thumbnail'
    image = store.artifact_path(p.id, 'thumbnail')
    with Image.open(image) as thumbnail:
        assert thumbnail.format == 'JPEG' and thumbnail.size == (3840, 2160)
        # Readable dark lettering must exist on the reserved light text side.
        pixels = thumbnail.convert('RGB').crop((100, 300, 1600, 1800))
        assert sum(pixels.convert('L').histogram()[:80]) > 1000
    assert image.stat().st_size < 2_000_000
    assert done.artifacts['thumbnail'].metadata['headline'] == 'NEVER ENOUGH?'
    with TestClient(create_app(tmp_path, worker_enabled=False)) as client:
        download = client.get(f'/api/projects/{p.id}/artifacts/thumbnail?download=true')
        assert download.status_code == 200
        assert download.headers['content-type'] == 'image/jpeg'
        assert 'attachment' in download.headers['content-disposition']
    pipeline.run(p.id)
    assert ai.thumbnail_plans == 1 and ai.thumbnail_images == 1
    assert ai.images == 4 and voice.calls == 1


def test_unknown_thumbnail_request_preserves_video_and_never_replays(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    original = ai.generate_image
    attempts = []
    def interrupted(scene, reference, destination):
        if scene.id == 0:
            attempts.append(scene)
            raise UnknownOutcome('Thumbnail request outcome is unknown')
        return original(scene, reference, destination)
    ai.generate_image = interrupted
    pipeline.run(p.id)
    state = store.get_project(p.id)
    assert state.status == 'needs_attention', 'Uncertain thumbnail work must stop completion'
    assert state.stage == 'thumbnail' and 'video' in state.artifacts
    assert 'thumbnail' not in state.artifacts
    Pipeline(store, providers=(ai, voice)).run(p.id)
    assert len(attempts) == 1
    assert store.get_project(p.id).status == 'needs_attention'


def test_thumbnail_regeneration_changes_only_thumbnail_work(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    pipeline.run(p.id)
    state = store.get_project(p.id)
    video, audio = state.artifacts['video'].fingerprint, state.artifacts['audio'].fingerprint
    with TestClient(create_app(tmp_path, worker_enabled=False)) as client:
        response = client.post(f'/api/projects/{p.id}/thumbnail?regenerate=true')
        assert response.status_code == 200, 'Existing episodes need thumbnail generation and regeneration'
    assert 'thumbnail' not in store.get_project(p.id).artifacts
    pipeline.run(p.id)
    state = store.get_project(p.id)
    assert state.status == 'completed', state.error
    assert state.artifacts['video'].fingerprint == video and state.artifacts['audio'].fingerprint == audio
    assert ai.images == 4 and voice.calls == 1
    assert ai.thumbnail_plans == 2 and ai.thumbnail_images == 2
    with TestClient(create_app(tmp_path, worker_enabled=False)) as client:
        client.patch(f'/api/projects/{p.id}/scenes/1', json={'voiceover': 'A changed gift.\n\n'})
    assert 'thumbnail' not in store.get_project(p.id).artifacts


def test_thumbnail_limit_stops_paid_artwork_without_losing_export(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    # All video requests fit; the thumbnail planning request cannot be reserved.
    settings = store.get_project(p.id).settings.model_copy(update={'budget_usd': 2.75})
    store.update_project(p.id, settings=settings)
    pipeline.run(p.id)
    state = store.get_project(p.id)
    assert state.status == 'needs_attention' and state.stage == 'thumbnail'
    assert 'video' in state.artifacts and 'thumbnail' not in state.artifacts
    assert ai.thumbnail_plans == 0 and ai.thumbnail_images == 0
    assert 'spending limit' in state.error


def test_thumbnail_only_uses_current_image_models_without_rebuilding_video(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    pipeline.run(p.id)
    before = store.get_project(p.id)
    store.save_settings(before.settings.model_copy(update={'text_model': 'new-thumbnail-writer', 'image_model': 'new-thumbnail-artist', 'voice_id': ''}))
    def forbidden(*args, **kwargs):
        raise AssertionError('Thumbnail-only work must not research, rewrite, replan or record the episode')
    ai.research = ai.write_script = ai.plan_scenes = voice.generate_speech = forbidden
    with TestClient(create_app(tmp_path, worker_enabled=False)) as client:
        assert client.post(f'/api/projects/{p.id}/thumbnail?regenerate=true').status_code == 200
    pipeline.run(p.id)
    after = store.get_project(p.id)
    assert after.status == 'completed', after.error
    assert after.settings.image_model == 'new-thumbnail-artist'
    assert after.settings.text_model == 'new-thumbnail-writer'
    assert after.artifacts['video'].fingerprint == before.artifacts['video'].fingerprint
    assert ai.images == 4 and voice.calls == 1


def test_thumbnail_plan_parses_actual_sdk_response_and_rejects_refusal(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    script = ai.write_script(p.topic, ai.research(p.topic), 200)
    responses = [
        {'type': 'output_text', 'text': json.dumps({'headline': 'Never enough?', 'visual': 'Katsu reaching for a star', 'prompt': 'Katsu on the right, white left half'}), 'annotations': []},
        {'type': 'refusal', 'refusal': 'Fixture provider refusal'},
    ]
    def transport(request):
        content = responses.pop(0)
        return httpx.Response(200, headers={'x-request-id': 'thumbnail-sdk-fixture'}, json={
            'id': 'resp_thumbnail_fixture', 'object': 'response', 'created_at': 1, 'status': 'completed', 'model': 'fixture-model',
            'output': [{'id': 'msg_fixture', 'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': [content]}],
        })
    client = OpenAI(api_key='fixture-only-not-real', max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    provider = OpenAIProvider('fixture-only', StudioSettings(), client=client)
    plan = provider.plan_thumbnail(script, {'style': 'Fixture style'})
    assert plan.headline == 'NEVER ENOUGH?'
    assert provider.last_metadata['request_id'] == 'thumbnail-sdk-fixture'
    with pytest.raises(ProviderError, match='no usable concept'):
        provider.plan_thumbnail(script, {'style': 'Fixture style'})
