from pathlib import Path
import base64
from PIL import Image
from katsu.models import Source, Script, Claim, Scene, Artifact, ThumbnailPlan
from katsu.content import scenes_from_plan
from katsu.providers.errors import UnknownOutcome
from test_audio import tone


class FixtureOpenAI:
    """Only the paid network boundary is replaced. Everything else runs normally."""
    last_metadata = {'request_id': 'fixture', 'usage': {}}

    def __init__(self, fail_image=False, on_image=None):
        self.images = 0
        self.thumbnail_plans = 0
        self.thumbnail_images = 0
        self.fail_image = fail_image
        self.on_image = on_image

    def research(self, topic):
        return [Source(title='Fixture evidence', url='https://example.org/fixture', evidence='Synthetic test only')]

    def write_script(self, topic, sources, target_words):
        return Script(title='Fixture video', narration='One gift.\n\nTwo gifts.\n\nThree gifts.\n\nEnough gifts.', sources=sources, claims=[Claim(claim='Fixture', source_urls=[sources[0].url])])

    def plan_scenes(self, script, scene_count, style):
        return scenes_from_plan(script, [{'first_paragraph': i, 'last_paragraph': i, 'visual': 'Fixture gift', 'prompt': f'Fixture {i}', 'label': None} for i in range(4)])

    def generate_image(self, scene, reference, destination):
        if scene.id == 0:
            self.thumbnail_images += 1
        else:
            self.images += 1
        if self.on_image:
            self.on_image()
        if self.fail_image:
            raise UnknownOutcome('Fixture interrupted paid image')
        destination.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (640, 360), ['red', 'green', 'blue', 'yellow'][scene.id-1]).save(destination)
        return Artifact(kind=f'scene_{scene.id}', path=destination.name, fingerprint='fixture')

    def plan_thumbnail(self, script, style):
        self.thumbnail_plans += 1
        return ThumbnailPlan(headline='NEVER ENOUGH?', visual='An expressive Katsu on the right with a gift', prompt='Fixture thumbnail artwork on the right, white left half.')


class FixtureVoice:
    last_metadata = {'request_id': 'fixture-voice'}

    def __init__(self):
        self.calls = 0

    def generate_speech(self, text, destination, previous_text='', next_text=''):
        self.calls += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        tone(destination, 2)
        n = len(text)
        return {'path': str(destination), 'text': text, 'alignment': {'characters': list(text), 'character_start_times_seconds': [i*1.8/n for i in range(n)], 'character_end_times_seconds': [(i+1)*1.8/n for i in range(n)]}, 'normalized_alignment': None}
