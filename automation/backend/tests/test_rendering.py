import json
from pathlib import Path
from PIL import Image
import pytest
from katsu.models import Scene, TimedWord
from katsu.rendering import render_video, verify_video
from test_audio import tone


def test_three_scene_real_video_has_expected_frame_boundaries_and_sound(tmp_path):
    scenes = []
    for i, color in enumerate(['red', 'green', 'blue'], 1):
        Image.new('RGB', (640, 360), color).save(tmp_path / f'{i}.png')
        scenes.append(Scene(id=i, narration_start=i-1, narration_end=i, voiceover=['Red', 'Green', 'Blue'][i-1], visual=color, prompt=color))
    audio = tmp_path / 'audio.wav'
    tone(audio, 1.5)
    words = [TimedWord(word='Red', start=0, end=.4), TimedWord(word='Green', start=.5, end=.9), TimedWord(word='Blue', start=1, end=1.4)]
    artifact = render_video(tmp_path, scenes, words, audio, {i: tmp_path / f'{i}.png' for i in range(1, 4)})
    report = json.loads((tmp_path / artifact.metadata['verification_path']).read_text())
    assert report['resolution'] == [1920, 1080]
    assert report['frames'] == 45
    assert report['image_order_checks'] == 3
    assert report['audio_codec'] == 'aac'
