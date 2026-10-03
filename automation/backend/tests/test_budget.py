import pytest
from katsu.models import ProjectCreate, StudioSettings
from katsu.store import Store
from katsu.budget import Budget, BudgetExceeded, UnknownOutcome


def test_reserved_and_unknown_requests_count_toward_limit_after_restart(tmp_path):
    s = Store(tmp_path)
    p = s.create_project(ProjectCreate(topic='A topic', budget_usd=1), StudioSettings(), 'one')
    b = Budget(s)
    b.reserve(p.id, 'image:one', .6)
    b.mark_unknown('image:one')
    with pytest.raises(UnknownOutcome):
        Budget(Store(tmp_path)).reserve(p.id, 'image:one', .6)
    with pytest.raises(BudgetExceeded):
        b.reserve(p.id, 'image:two', .5)
    assert s.get_project(p.id).estimated_committed_usd == .6


def test_confirmed_failed_request_can_be_retried_without_double_reservation(tmp_path):
    s = Store(tmp_path)
    p = s.create_project(ProjectCreate(topic='A topic', budget_usd=1), StudioSettings(), 'one')
    b = Budget(s)
    b.reserve(p.id, 'first', .5)
    b.settle('first', {'failed': True})
    b.reserve(p.id, 'first', .5)
    b.settle('first', {'request_id': 'safe-metadata'})
    assert s.get_project(p.id).estimated_committed_usd == .5
