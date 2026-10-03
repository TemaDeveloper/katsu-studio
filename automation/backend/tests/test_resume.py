from test_pipeline import make
from katsu.budget import Budget
from katsu.pipeline import Pipeline


def test_unknown_paid_request_cannot_be_replayed_after_restart(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path, fail_image=True)
    pipeline.run(p.id)
    assert store.get_project(p.id).status == 'needs_attention'
    ai.fail_image = False
    Pipeline(store, providers=(ai, voice)).run(p.id)
    assert ai.images == 1
    assert store.get_project(p.id).status == 'needs_attention'


def test_image_model_change_invalidates_only_images(tmp_path):
    store, p, pipeline, ai, voice = make(tmp_path)
    pipeline.run(p.id)
    settings = store.get_project(p.id).settings
    settings.image_model = 'other-accessible-model'
    store.update_project(p.id, settings=settings)
    pipeline.run(p.id)
    assert store.get_project(p.id).status == 'completed'
    assert ai.images == 8 and voice.calls == 1
