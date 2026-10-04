import json
import httpx
import pytest
from openai import OpenAI
from fastapi.testclient import TestClient
from katsu.main import create_app
from katsu.models import ProjectCreate, StudioSettings, Script, Source, Claim, Scene
from katsu.content import scenes_from_plan
from katsu.providers.openai import OpenAIProvider
from katsu.store import Store
from test_pipeline import make


def test_new_projects_keep_chosen_minutes_and_wait_for_script_before_counting(tmp_path):
    client = TestClient(create_app(tmp_path, worker_enabled=False))
    settings = client.get('/api/settings').json()['settings']
    settings['scene_count'] = 72  # A saved preference from the previous version.
    client.put('/api/settings', json=settings)
    project = client.post('/api/projects', json={'topic': 'Why do goals keep changing?', 'target_seconds': 180, 'scene_count': 24}).json()
    assert project['settings']['target_seconds'] == 180
    assert project['total_assets'] == 0, 'No illustrations are planned before the narration exists'
    assert project['settings']['scene_count'] is None
    assert project['scene_planning'] == 'automatic'


def test_script_drives_two_images_and_exact_narration_coverage(tmp_path):
    store, project, pipeline, ai, voice = make(tmp_path)
    settings = project.settings.model_copy(update={'target_seconds': 180})
    store.update_project(project.id, settings=settings)
    calls = []
    original_write = ai.write_script
    def write(topic, sources, target_words):
        calls.append(('writing', target_words))
        return original_write(topic, sources, target_words)
    def plan(script, scene_count, style):
        calls.append(('planning', scene_count))
        # Two related gift paragraphs share each illustration.
        return scenes_from_plan(script, [
            {'first_paragraph': 0, 'last_paragraph': 1, 'visual': 'Two gifts', 'prompt': 'Opening gifts'},
            {'first_paragraph': 2, 'last_paragraph': 3, 'visual': 'Enough gifts', 'prompt': 'Recognizing enough'},
        ])
    ai.write_script, ai.plan_scenes = write, plan
    pipeline.run(project.id)
    done = store.get_project(project.id)
    assert done.status == 'completed', done.error
    assert calls == [('writing', 435), ('planning', None)]
    assert done.total_assets == done.completed_assets == 2
    assert ai.images == 2
    scenes = json.loads(store.artifact_path(project.id, 'scenes').read_text())
    assert [s['voiceover'] for s in scenes] == ['One gift.\n\nTwo gifts.\n\n', 'Three gifts.\n\nEnough gifts.']
    pipeline.run(project.id)
    assert len(calls) == 2 and ai.images == 2 and voice.calls == 1


def test_excessive_scene_plan_stops_before_any_image_purchase(tmp_path):
    store, project, pipeline, ai, voice = make(tmp_path)
    source = ai.research(project.topic)[0]
    script = Script(title='Too many scenes', narration='word ' * 121, sources=[source], claims=[Claim(claim='Fixture', source_urls=[source.url])])
    ai.write_script = lambda *args: script
    ai.plan_scenes = lambda *args: [Scene(id=i+1, narration_start=i*5, narration_end=(i+1)*5, voiceover='word ', visual='Gift', prompt='Gift') for i in range(121)]
    pipeline.run(project.id)
    done = store.get_project(project.id)
    assert done.status == 'needs_attention'
    assert done.stage == 'planning' and '120' in done.error
    assert ai.images == voice.calls == 0


def test_automatic_sdk_prompts_follow_script_length_and_semantic_beats():
    requests = []
    draft = {'title': 'Gifts', 'paragraphs': ['One gift.', 'Two gifts.', 'Three gifts.', 'Enough gifts.'], 'claims': [{'claim': 'Fixture', 'source_urls': ['https://example.org/fixture']}]}
    plan = {'scenes': [{'first_paragraph': 0, 'last_paragraph': 1, 'visual': 'Gifts', 'prompt': 'Gifts', 'label': None}, {'first_paragraph': 2, 'last_paragraph': 3, 'visual': 'Enough', 'prompt': 'Enough', 'label': None}]}
    def transport(request):
        requests.append(json.loads(request.content))
        payload = draft if len(requests) == 1 else plan
        return httpx.Response(200, json={'id': 'resp_fixture', 'object': 'response', 'created_at': 1, 'status': 'completed', 'model': 'fixture', 'output': [{'id': 'msg_fixture', 'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': [{'type': 'output_text', 'text': json.dumps(payload), 'annotations': []}]}]})
    client = OpenAI(api_key='fixture-only', max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    provider = OpenAIProvider('fixture-only', StudioSettings(), client=client)
    script = provider.write_script('Gifts', [Source(title='Fixture', url='https://example.org/fixture', evidence='Fixture')], 8)
    assert 'Aim for' not in requests[0]['input'][1]['content']
    scenes = provider.plan_scenes(script, None, {'style': 'Fixture'})
    assert len(scenes) == 2
    assert ''.join(s.voiceover for s in scenes) == script.narration
    assert 'Aim for' not in requests[1]['input'][1]['content']


def test_old_submission_retries_return_saved_episode_without_replanning(tmp_path):
    store = Store(tmp_path)
    request = ProjectCreate(topic='Old browser submission', scene_count=24)
    project = store.create_project(request, StudioSettings(), 'old-click')
    # Simulate a pre-upgrade row without the new planning marker.
    payload = project.model_dump()
    payload.pop('scene_planning', None)
    payload['settings']['scene_count'] = 24
    payload['total_assets'] = 24
    store.db.execute('UPDATE projects SET payload=? WHERE id=?', (json.dumps(payload), project.id))
    store.db.commit()
    restored = store.create_project(request, StudioSettings(), 'old-click')
    assert restored.id == project.id and restored.total_assets == 24
    assert restored.scene_planning == 'legacy'


def test_resuming_legacy_episode_keeps_paid_script_and_scene_cache(tmp_path):
    store, project, pipeline, ai, voice = make(tmp_path)
    settings = project.settings.model_copy(update={'scene_count': 4})
    # Old serialized rows use the legacy fingerprints including their requested count.
    store.update_project(project.id, scene_planning='legacy', settings=settings)
    pipeline.run(project.id)
    assert store.get_project(project.id).status == 'completed'
    def forbidden(*args):
        raise AssertionError('Saved legacy narration and scenes must not be purchased again')
    ai.research = ai.write_script = ai.plan_scenes = forbidden
    pipeline.run(project.id)
    assert store.get_project(project.id).status == 'completed'
    assert ai.images == 4 and voice.calls == 1


def test_reimporting_a_pre_upgrade_episode_reuses_its_existing_identity(tmp_path):
    from katsu.import_existing import import_existing
    from katsu.legacy import load
    workspace = tmp_path / 'workspace'
    output = workspace / 'output'
    output.mkdir(parents=True)
    video = output / 'final_video.mp4'
    video.write_bytes(b'Previously imported video fixture')
    (output / 'PRODUCTION_MANIFEST.json').write_text(json.dumps({'title': 'Previously imported episode'}))
    store = Store(tmp_path / 'data')
    original = store.create_project(ProjectCreate(topic='Previously imported episode', scene_count=120), StudioSettings(), 'existing:' + load('compose_video').digest(video))
    store.update_project(original.id, imported=True, status='completed')
    assert import_existing(store, workspace).id == original.id
    assert len(store.list_projects()) == 1


def test_pre_upgrade_api_retry_without_explicit_scene_count_reuses_old_default_hash(tmp_path):
    store = Store(tmp_path)
    original = store.create_project(ProjectCreate(topic='Old API topic', scene_count=72), StudioSettings(), 'old-api-click')
    payload = original.model_dump()
    payload.pop('scene_planning')
    payload['settings']['scene_count'] = 72
    store.db.execute('UPDATE projects SET payload=? WHERE id=?', (json.dumps(payload), original.id))
    store.db.commit()
    # Old parsing supplied 72 even when the API caller did not send that field.
    retry = store.create_project(ProjectCreate(topic='Old API topic'), StudioSettings(), 'old-api-click')
    assert retry.id == original.id and retry.settings.scene_count == 72
    assert len(store.list_projects()) == 1
    with pytest.raises(ValueError, match='different topic'):
        store.create_project(ProjectCreate(topic='Different API topic'), StudioSettings(), 'old-api-click')
