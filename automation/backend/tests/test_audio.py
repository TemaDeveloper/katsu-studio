from pathlib import Path
import wave
import math
import struct
import pytest
from katsu.audio import join_audio, prepare_narration, duration


def tone(path, seconds):
    with wave.open(str(path), 'wb') as f:
        f.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
        f.writeframes(b''.join(struct.pack('<h', int(5000*math.sin(i*2*math.pi*440/44100))) for i in range(round(seconds*44100))))


def test_join_uses_decoded_offsets_and_checks_alignment_bounds(tmp_path):
    first, second = tmp_path / 'one.wav', tmp_path / 'two.wav'
    tone(first, .5)
    tone(second, .25)
    dest = tmp_path / 'joined.wav'
    assert join_audio([first, second], dest) == [0, .5]
    assert duration(dest) == pytest.approx(.75, abs=.001)
    alignment = {'characters': ['a'], 'character_start_times_seconds': [0], 'character_end_times_seconds': [.2]}
    audio, words = prepare_narration(tmp_path, [{'path': str(first), 'text': 'a', 'alignment': alignment}, {'path': str(second), 'text': 'a', 'alignment': alignment}], {'remove_pauses': False})
    assert [w.start for w in words] == [0, .5]
    alignment['character_end_times_seconds'] = [2]
    with pytest.raises(ValueError, match='duration'):
        prepare_narration(tmp_path, [{'path': str(first), 'text': 'a', 'alignment': alignment}], {'remove_pauses': False}, allow_whisper=False)


def test_missing_alignment_requires_actual_audio_transcription(tmp_path):
    path = tmp_path / 'one.wav'
    tone(path, .3)
    with pytest.raises(ValueError, match='alignment'):
        prepare_narration(tmp_path, [{'path': str(path), 'text': 'Hello', 'alignment': None}], {'remove_pauses': False}, allow_whisper=False)
