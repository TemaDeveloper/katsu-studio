import re
from urllib.parse import urlparse
from .models import Scene, Script

MAX_SCENES = 120


def validate_script(script, sources):
    if not sources or not script.narration.strip() or not script.title.strip():
        raise ValueError('Research and a complete narration are required.')
    known = {s.url for s in sources}
    if any(urlparse(u).scheme not in ('https', 'http') for u in known):
        raise ValueError('Research contains an invalid source URL.')
    if not script.claims or any(not c.source_urls or not set(c.source_urls) <= known for c in script.claims):
        raise ValueError('Every factual claim must refer to an actual research source.')
    if not {s.url for s in script.sources} <= known:
        raise ValueError('Script cites an unresearched source.')


def paragraph_spans(text):
    return [(m.start(), m.end()) for m in re.finditer(r'.+?(?:\n\n|$)', text, re.S)]


def scenes_from_plan(script, plans):
    spans = paragraph_spans(script.narration)
    scenes = []
    for i, p in enumerate(plans, 1):
        first, last = p['first_paragraph'], p['last_paragraph']
        if not (0 <= first <= last < len(spans)):
            raise ValueError('Scene paragraph range is invalid.')
        start, end = spans[first][0], spans[last][1]
        scenes.append(Scene(id=i, narration_start=start, narration_end=end, voiceover=script.narration[start:end], visual=p['visual'], prompt=p['prompt'], label=p.get('label')))
    validate_scene_spans(script, scenes)
    return scenes


def validate_scene_spans(script: Script, scenes: list[Scene]):
    cursor = 0
    if not scenes:
        raise ValueError('Scene planning returned no scenes.')
    if len(scenes) > MAX_SCENES:
        raise ValueError(f'Scene planning exceeded the {MAX_SCENES}-illustration production limit. Group related narration into fewer visual scenes.')
    for i, scene in enumerate(scenes, 1):
        if scene.id != i or scene.narration_start != cursor or scene.narration_end <= cursor:
            raise ValueError('Scenes must cover the narration in contiguous order.')
        if scene.voiceover != script.narration[cursor:scene.narration_end] or not scene.voiceover.strip():
            raise ValueError('A scene rewrote or omitted canonical narration.')
        cursor = scene.narration_end
    if cursor != len(script.narration):
        raise ValueError('Scenes must cover all narration in contiguous order.')
