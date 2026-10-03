import pytest
from katsu.models import Script, Source, Claim, Scene
from katsu.content import validate_script, validate_scene_spans, scenes_from_plan


def script():
    return Script(title='Enough?', narration='You wanted 2 things.\n\nNow you want more.', sources=[Source(title='Study', url='https://example.org/study', evidence='Evidence')], claims=[Claim(claim='Adaptation happens', source_urls=['https://example.org/study'])])


def test_scene_planning_keeps_numerals_and_every_character():
    s = script()
    scenes = scenes_from_plan(s, [{'first_paragraph': 0, 'last_paragraph': 0, 'visual': 'Two gifts', 'prompt': 'Gifts', 'label': None}, {'first_paragraph': 1, 'last_paragraph': 1, 'visual': 'More gifts', 'prompt': 'Gifts', 'label': None}])
    assert scenes[0].voiceover == 'You wanted 2 things.\n\n'
    assert scenes[1].narration_start == 22
    assert ''.join(x.voiceover for x in scenes) == s.narration
    scenes[1].narration_start -= 1
    with pytest.raises(ValueError, match='contiguous'):
        validate_scene_spans(s, scenes)


def test_empty_research_and_unresearched_citations_are_rejected():
    s = script()
    with pytest.raises(ValueError):
        validate_script(s, [])
    s.claims[0].source_urls = ['https://made-up.example/study']
    with pytest.raises(ValueError, match='source'):
        validate_script(s, script().sources)
