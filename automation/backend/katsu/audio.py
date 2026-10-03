from pathlib import Path
import json
import subprocess
import sys
import wave
from .config import WORKSPACE
from .models import TimedWord
from .timing import alignment_to_words, remap_words


def command(args):
    result = subprocess.run([str(a) for a in args], capture_output=True, timeout=1800)
    if result.returncode:
        raise ValueError('Audio/video processing failed: ' + result.stderr.decode(errors='replace')[-1200:])
    return result.stdout


def duration(path):
    return float(command(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', path]))


def join_audio(chunks, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    offsets, frames = [], 0
    temporary = destination.with_suffix('.part.wav')
    with wave.open(str(temporary), 'wb') as out:
        out.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
        for path in chunks:
            decoded = command(['ffmpeg', '-v', 'error', '-i', path, '-map', '0:a:0', '-vn', '-ac', 1, '-ar', 44100, '-f', 's16le', '-'])
            if not decoded:
                raise ValueError('A narration chunk contains no decoded audio.')
            offsets.append(frames / 44100)
            out.writeframesraw(decoded)
            frames += len(decoded) // 2
    temporary.replace(destination)
    return offsets


def prepare_narration(project_dir, chunks, pause_settings, allow_whisper=True):
    joined = project_dir / 'joined.wav'
    offsets = join_audio([Path(c['path']) for c in chunks], joined)
    words = []
    try:
        for chunk, offset in zip(chunks, offsets):
            local = alignment_to_words(chunk)
            chunk_duration = duration(Path(chunk['path']))
            if any(w.end > chunk_duration + .1 for w in local):
                raise ValueError('Word alignment extends beyond the chunk duration.')
            words.extend(TimedWord(word=w.word, start=w.start+offset, end=min(w.end, chunk_duration)+offset) for w in local)
    except ValueError:
        if not allow_whisper:
            raise
        try:
            import whisper
        except ImportError:
            raise ValueError('Narration alignment is missing or invalid. Install optional openai-whisper for local transcription, or regenerate narration.') from None
        result = whisper.load_model('base.en').transcribe(str(joined), word_timestamps=True, language='en', fp16=False)
        words = [TimedWord(word=w['word'], start=w['start'], end=w['end']) for s in result['segments'] for w in s.get('words', [])]
        if not words:
            raise ValueError('Local transcription returned no word alignment.')
    if not pause_settings.get('remove_pauses', True):
        return joined, words
    edited = project_dir / 'narration.wav'
    command([sys.executable, WORKSPACE / 'remove_reader_pauses.py', joined, '-o', edited, '--overwrite',
             '--threshold-db', pause_settings.get('pause_threshold_db', -45),
             '--min-pause', pause_settings.get('minimum_pause_seconds', .35),
             '--keep-pause', pause_settings.get('retained_pause_seconds', .12)])
    report = json.loads(edited.with_suffix('.pauses.json').read_text())
    words = remap_words(words, report['retained_segments'])
    if words[-1].end > duration(edited) + .05:
        raise ValueError('Edited alignment exceeds the narration duration.')
    return edited, words
