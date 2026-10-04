import pytest
from katsu.models import ProjectCreate, StudioSettings, Artifact
from katsu.store import Store


def test_artifact_paths_are_contained_even_with_symlinks(tmp_path):
    store = Store(tmp_path / 'data')
    p = store.create_project(ProjectCreate(topic='A topic'), StudioSettings(), 'one')
    outside = tmp_path / 'private.txt'
    outside.write_text('private')
    store.project_dir(p.id).joinpath('escape').symlink_to(outside)
    for path in ('../private.txt', str(outside), 'escape'):
        with pytest.raises(ValueError):
            store.register_artifact(p.id, Artifact(kind='script', path=path, fingerprint='test'))
    inside = store.project_dir(p.id) / 'script.txt'
    inside.write_text('approved')
    store.register_artifact(p.id, Artifact(kind='script', path='script.txt', fingerprint='test'))
    assert Store(store.root).artifact_path(p.id, 'script').read_text() == 'approved'


def test_projects_take_a_settings_snapshot_and_cannot_inject_keys(tmp_path):
    store = Store(tmp_path)
    settings = StudioSettings(voice_id='original')
    p = store.create_project(ProjectCreate(topic='A topic'), settings, 'one')
    settings.voice_id = 'different'
    assert store.get_project(p.id).settings.voice_id == 'original'
    assert 'secrets' not in store.get_project(p.id).model_dump()
