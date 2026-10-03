from test_pipeline import make
from helpers import FixtureOpenAI, FixtureVoice
from katsu.pipeline import Pipeline


def test_failed_settings_change_never_exposes_stale_final_export(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    pipeline.run(p.id)
    assert 'video' in store.get_project(p.id).artifacts
    settings = store.get_project(p.id).settings
    settings.image_model = 'changed-model'
    store.update_project(p.id, settings=settings)
    ai.fail_image = True
    pipeline.run(p.id)
    state = store.get_project(p.id)
    assert state.status == 'needs_attention'
    assert 'video' not in state.artifacts
