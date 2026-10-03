import math
import re
from .models import TimedWord


def chunk_narration(text, max_characters=2500):
    if not text.strip() or max_characters < 20:
        raise ValueError('Narration or chunk limit is invalid.')
    spans, start = [], 0
    while start < len(text):
        limit = min(len(text), start + max_characters)
        end = limit
        if limit < len(text):
            fragment = text[start:limit]
            boundaries = [m.end() for m in re.finditer(r'\n\n|[.!?](?:\s+|$)', fragment)]
            if boundaries:
                end = start + boundaries[-1]
            else:
                last_space = fragment.rfind(' ')
                if last_space > 0:
                    end = start + last_space + 1
        spans.append((start, end))
        start = end
    return spans


def alignment_to_words(payload):
    alignment = payload.get('alignment') or payload.get('normalized_alignment')
    if not alignment:
        raise ValueError('Narration has no character alignment.')
    chars = alignment.get('characters', [])
    starts = alignment.get('character_start_times_seconds', [])
    ends = alignment.get('character_end_times_seconds', [])
    if not chars or len(chars) != len(starts) or len(chars) != len(ends) or any(not isinstance(c, str) or len(c) != 1 for c in chars):
        raise ValueError('Narration character alignment has malformed arrays.')
    text = ''.join(chars)
    if payload.get('alignment') and text.strip() != payload.get('text', text).strip():
        raise ValueError('Narration alignment does not cover the requested text.')
    previous = -1
    for start, end in zip(starts, ends):
        if not (isinstance(start, (float, int)) and isinstance(end, (float, int)) and math.isfinite(start) and math.isfinite(end) and 0 <= start <= end and start >= previous):
            raise ValueError('Narration character alignment contains impossible times.')
        previous = start
    words = [TimedWord(word=m.group(), start=round(starts[m.start()], 6), end=round(ends[m.end()-1], 6)) for m in re.finditer(r'\S+', text)]
    if not words:
        raise ValueError('Narration alignment contains no words.')
    return words


def remap_words(words, retained_segments):
    if not retained_segments:
        raise ValueError('No audio was retained.')
    mapped = []
    previous = -1
    for word in words:
        if word.start < 0 or word.end > retained_segments[-1]['source_end'] + .1:
            raise ValueError('A word lies outside the source audio duration.')
        pieces = []
        for s in retained_segments:
            a, b = max(word.start, s['source_start']), min(word.end, s['source_end'])
            if b > a:
                pieces.append((s['output_start'] + a - s['source_start'], s['output_start'] + b - s['source_start']))
        if not pieces:
            raise ValueError('A spoken word was wholly removed by pause cleanup. Use a lower silence threshold or disable cleanup.')
        start, end = round(pieces[0][0], 6), round(pieces[-1][1], 6)
        if start < previous or end > retained_segments[-1]['output_end'] + .001:
            raise ValueError('Edited word timing is out of order or beyond the audio duration.')
        previous = start
        mapped.append(TimedWord(word=word.word, start=start, end=end))
    return mapped
