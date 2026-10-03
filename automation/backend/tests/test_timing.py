import pytest
from katsu.timing import chunk_narration, alignment_to_words, remap_words
from katsu.models import TimedWord


def test_chunk_boundaries_preserve_all_text_and_obey_provider_limit():
    text = 'First sentence. Second sentence.\n\nThird paragraph. Last one.'
    spans = chunk_narration(text, 32)
    assert ''.join(text[a:b] for a, b in spans) == text
    assert spans[0] == (0, 32)
    assert all(b-a <= 32 for a, b in spans)


def test_normalized_alignment_is_used_without_invented_word_times():
    text = 'two gifts'
    data = {'text': '2 gifts', 'alignment': None, 'normalized_alignment': {'characters': list(text), 'character_start_times_seconds': [i*.1 for i in range(9)], 'character_end_times_seconds': [(i+1)*.1 for i in range(9)]}}
    words = alignment_to_words(data)
    assert [(w.word, w.start, w.end) for w in words] == [('two', 0, .3), ('gifts', .4, .9)]
    data['normalized_alignment']['character_end_times_seconds'] = [0]
    with pytest.raises(ValueError):
        alignment_to_words(data)


def test_removed_silence_maps_crossing_words_and_rejects_words_wholly_removed():
    segments = [{'source_start': 0, 'source_end': 1, 'output_start': 0, 'output_end': 1}, {'source_start': 2, 'source_end': 4, 'output_start': 1, 'output_end': 3}]
    mapped = remap_words([TimedWord(word='crossing', start=.9, end=2.2)], segments)
    assert mapped[0].start == .9
    assert mapped[0].end == pytest.approx(1.2)
    with pytest.raises(ValueError, match='removed'):
        remap_words([TimedWord(word='lost', start=1.3, end=1.6)], segments)
    with pytest.raises(ValueError):
        remap_words([TimedWord(word='outside', start=4, end=5)], segments)
