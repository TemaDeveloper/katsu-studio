import io
import json
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from katsu.main import create_app
from katsu.pipeline import Pipeline
from katsu.models import Artifact
from katsu.providers.errors import UnknownOutcome
from test_pipeline import make


class Keys:
    def get(self, provider):
        return 'fixture-key' if provider == 'openai' else None

    def status(self):
        return {'openai': True, 'elevenlabs': False}


def image_bytes(color='purple', size=(640, 360)):
    out = io.BytesIO()
    Image.new('RGB', size, color).save(out, 'PNG')
    return out.getvalue()


@pytest.fixture
def episode(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    pipeline.run(p.id)
    assert store.get_project(p.id).status == 'completed'
    client = TestClient(create_app(tmp_path, worker_enabled=False, credentials=Keys()))
    return store, p.id, client, pipeline, ai, voice


def upload(client, id, kind, base=None, data=None):
    if base is None:
        base = client.get(f'/api/projects/{id}').json()['artifacts'][kind]['fingerprint']
    return client.post(f'/api/projects/{id}/artwork/{kind}/draft/upload',
        content=data or image_bytes(), headers={'Content-Type': 'image/png', 'X-Base-Fingerprint': base})


def test_upload_preview_apply_and_restore_reuse_saved_recording(episode):
    store, id, c, pipeline, ai, voice = episode
    before = store.get_project(id)
    old_video = store.artifact_path(id, 'video')
    draft = upload(c, id, 'scene_1')
    assert draft.status_code == 201, draft.text
    assert store.get_project(id).artifacts == before.artifacts | {
        'artwork_draft_scene_1': store.get_project(id).artifacts['artwork_draft_scene_1']}
    applied = c.post(f'/api/projects/{id}/artwork/scene_1/apply', json={'draft_id': draft.json()['draft_id']})
    assert applied.status_code == 200, applied.text
    assert applied.json()['render_only'] is True
    assert old_video.exists() and store.artifact_path(id, 'video') == old_video
    # This export deliberately has no provider or API keys available.
    Pipeline(store).run(id)
    done = store.get_project(id)
    assert done.status == 'completed', done.error
    for kind in ('audio', 'words', 'script', 'scene_2', 'scene_3', 'scene_4', 'thumbnail'):
        assert done.artifacts[kind] == before.artifacts[kind]
    assert done.artifacts['video'].fingerprint != before.artifacts['video'].fingerprint
    assert (ai.images, voice.calls) == (4, 1)
    assert json.loads(store.artifact_path(id, 'verification').read_text())['image_order_checks'] == 4
    versions = c.get(f'/api/projects/{id}/artwork/scene_1/versions').json()
    assert len(versions) == 2 and sum(x['current'] for x in versions) == 1
    restored = c.post(f'/api/projects/{id}/artwork/scene_1/restore', json={'fingerprint': before.artifacts['scene_1'].fingerprint})
    assert restored.status_code == 200
    Pipeline(store).run(id)
    assert store.get_project(id).status == 'completed'
    assert store.artifact_path(id, 'scene_1') == store.contained(id, before.artifacts['scene_1'].path)


def test_complete_thumbnail_upload_preserves_composition_and_video(episode):
    store, id, c, _, _, _ = episode
    before = store.get_project(id)
    draft = upload(c, id, 'thumbnail', data=image_bytes('coral', (1280, 720)))
    assert draft.status_code == 201, draft.text
    assert c.post(f'/api/projects/{id}/artwork/thumbnail/apply', json={'draft_id': draft.json()['draft_id']}).status_code == 200
    done = store.get_project(id)
    assert done.status == 'completed' and not done.render_only
    assert done.artifacts['video'] == before.artifacts['video']
    assert done.artifacts['audio'] == before.artifacts['audio']
    with Image.open(store.artifact_path(id, 'thumbnail')) as img:
        assert img.size == (3840, 2160) and img.format == 'JPEG'
        assert img.getpixel((200, 1000))[0] > 240 and img.getpixel((200, 1000))[1] < 150
    assert store.artifact_path(id, 'thumbnail').stat().st_size < 2_000_000


def test_invalid_upload_and_stale_preview_never_overwrite_current(episode):
    store, id, c, _, _, _ = episode
    before = store.get_project(id)
    assert upload(c, id, 'scene_1', data=b'not a png').status_code == 422
    assert upload(c, id, 'scene_1', data=image_bytes(size=(1, 1))).status_code == 422
    assert upload(c, id, 'scene_1', base='stale').status_code == 409
    assert store.get_project(id).artifacts == before.artifacts
    first = upload(c, id, 'thumbnail').json()
    second = upload(c, id, 'thumbnail', data=image_bytes('orange')).json()
    assert c.post(f'/api/projects/{id}/artwork/thumbnail/apply', json={'draft_id': first['draft_id']}).status_code == 409
    assert c.post(f'/api/projects/{id}/artwork/thumbnail/apply', json={'draft_id': second['draft_id']}).status_code == 200
    assert c.post(f'/api/projects/{id}/artwork/thumbnail/restore', json={'fingerprint': '../../secrets'}).status_code in (404, 422)


class EditAI:
    last_metadata = {'request_id': 'fixture-edit'}

    def __init__(self, fail=False):
        self.calls = 0
        self.input = None
        self.fail = fail

    def edit_image(self, instructions, current, destination):
        self.calls += 1
        self.input = current.read_bytes()
        if self.fail:
            raise UnknownOutcome('Fixture lost edit response')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(image_bytes('orange', (1024, 1024)))
        if getattr(self, 'on_edit', None):
            self.on_edit()
        return Artifact(kind='edit', path=destination.name, fingerprint='fixture-edit')


def test_ai_edit_is_paid_once_uses_current_asset_and_only_creates_preview(episode):
    store, id, c, _, _, voice = episode
    before = store.get_project(id)
    ai = EditAI()
    url = f'/api/projects/{id}/artwork/thumbnail/draft'
    payload = {'instructions': 'Make the headline larger.', 'base_fingerprint': before.artifacts['thumbnail'].fingerprint}
    first = c.post(url, json=payload, headers={'Idempotency-Key': 'edit-one'})
    assert first.status_code == 202, first.text
    pipeline = Pipeline(store, providers=(ai, voice))
    pipeline.run(id)
    assert ai.input == store.artifact_path(id, 'thumbnail').read_bytes()
    assert store.get_project(id).artifacts['thumbnail'] == before.artifacts['thumbnail']
    assert store.get_project(id).status == 'completed'
    draft = c.get(url).json()
    assert draft['origin'] == 'ai' and draft['draft_id']
    again = c.post(url, json=payload, headers={'Idempotency-Key': 'edit-one'})
    assert again.status_code == 200
    assert ai.calls == 1
    assert c.post(url, json={**payload, 'instructions': 'A different request'}, headers={'Idempotency-Key': 'edit-one'}).status_code == 409


def test_uncertain_ai_edit_cannot_be_bypassed_with_a_new_submission(episode):
    store, id, c, _, _, voice = episode
    ai = EditAI(fail=True)
    payload = {'instructions': 'Make the eyes bigger.', 'base_fingerprint': store.get_project(id).artifacts['scene_1'].fingerprint}
    url = f'/api/projects/{id}/artwork/scene_1/draft'
    assert c.post(url, json=payload, headers={'Idempotency-Key': 'unknown-one'}).status_code == 202
    pipeline = Pipeline(store, providers=(ai, voice))
    pipeline.run(id)
    assert store.get_project(id).status == 'needs_attention'
    pipeline.run(id)
    assert ai.calls == 1
    assert c.post(url, json=payload, headers={'Idempotency-Key': 'unknown-two'}).status_code == 409
    assert c.post(f'/api/projects/{id}/artwork/scene_1/draft/discard').status_code == 409
    assert c.post(f'/api/projects/{id}/acknowledge-unknown').status_code == 200
    assert c.post(f'/api/projects/{id}/artwork/scene_1/draft/discard').status_code == 200


def test_edits_rejected_while_project_is_queued(episode):
    store, id, c, _, _, _ = episode
    store.update_project(id, status='queued')
    assert upload(c, id, 'thumbnail').status_code == 409


def test_ai_preview_after_stopped_export_preserves_pending_rebuild(episode):
    store, id, c, _, _, voice = episode
    store.update_project(id, status='cancelled', stage='rendering', render_only=True)
    value = {'instructions': 'Make the eyes bigger.', 'base_fingerprint': store.get_project(id).artifacts['scene_1'].fingerprint}
    response = c.post(f'/api/projects/{id}/artwork/scene_1/draft', json=value, headers={'Idempotency-Key': 'after-stop'})
    assert response.status_code == 202
    assert store.get_project(id).render_only is False
    ai = EditAI()
    Pipeline(store, providers=(ai, voice)).run(id)
    done = store.get_project(id)
    assert ai.calls == 1
    assert done.artwork_edit is None and done.render_only is True
    assert done.status == 'cancelled'
    assert 'artwork_draft_scene_1' in done.artifacts


def test_settled_preview_recovers_after_cancellation_without_any_key(episode):
    store, id, c, _, _, voice = episode
    ai = EditAI()
    pipeline = Pipeline(store, providers=(ai, voice))
    ai.on_edit = lambda: pipeline.cancel(id)
    value = {'instructions': 'Make the eyes bigger.', 'base_fingerprint': store.get_project(id).artifacts['scene_1'].fingerprint}
    assert c.post(f'/api/projects/{id}/artwork/scene_1/draft', json=value, headers={'Idempotency-Key': 'cancel-edit'}).status_code == 202
    pipeline.run(id)
    assert store.get_project(id).status == 'cancelled'
    assert c.post(f'/api/projects/{id}/resume').status_code == 200
    Pipeline(store).run(id)
    assert store.get_project(id).status == 'completed', store.get_project(id).error
    assert store.get_project(id).artwork_edit is None
    assert ai.calls == 1


@pytest.mark.parametrize('operation', ['regenerate', 'wording', 'thumbnail'])
def test_normal_production_action_can_replace_a_stopped_saved_export(episode, operation):
    store, id, c, pipeline, ai, voice = episode
    store.update_project(id, status='cancelled', stage='rendering', render_only=True)
    if operation == 'regenerate':
        response = c.post(f'/api/projects/{id}/scenes/1/regenerate')
    elif operation == 'wording':
        response = c.patch(f'/api/projects/{id}/scenes/1', json={'voiceover': 'A changed gift.\n\n'})
    else:
        response = c.post(f'/api/projects/{id}/thumbnail?regenerate=true')
    assert response.status_code == 200
    assert store.get_project(id).render_only is False
    if operation == 'wording':
        assert c.post(f'/api/projects/{id}/resume').status_code == 200
    pipeline.run(id)
    assert store.get_project(id).status == 'completed', store.get_project(id).error
    assert ai.images == (5 if operation == 'regenerate' else 4)
    assert voice.calls == (2 if operation == 'wording' else 1)
