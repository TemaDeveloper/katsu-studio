import pytest
import httpx
from katsu.models import StudioSettings
from katsu.providers.elevenlabs import ElevenLabsProvider
from katsu.providers.openai import decode_image, extract_sources
from katsu.providers.errors import ProviderError, UnknownOutcome


def test_voice_timeout_is_an_unknown_paid_outcome_and_not_retried(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout('timeout')
    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ElevenLabsProvider('private-key', StudioSettings(voice_id='selected-voice'), client=client)
    with pytest.raises(UnknownOutcome):
        provider.generate_speech('Hello.', tmp_path / 'audio.mp3')
    assert len(calls) == 1
    assert not (tmp_path / 'audio.mp3').exists()


def test_malformed_media_is_rejected_before_registration(tmp_path):
    with pytest.raises(ProviderError):
        decode_image('bm90IGFuIGltYWdl', tmp_path / 'image.png')
    response = {'audio_base64': 'bm90IGF1ZGlv', 'alignment': None, 'normalized_alignment': None}
    provider = ElevenLabsProvider('secret-key', StudioSettings(voice_id='voice'), client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response))))
    with pytest.raises(ProviderError):
        provider.generate_speech('Hello.', tmp_path / 'audio.mp3')


def test_research_uses_real_response_citations_not_generated_links():
    payload = {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Adaptation is variable. [1]', 'annotations': [{'type': 'url_citation', 'url': 'https://example.org/paper', 'title': 'Paper', 'start_index': 23, 'end_index': 26}]}]}]}
    assert extract_sources(payload)[0].url == 'https://example.org/paper'
    with pytest.raises(ProviderError):
        extract_sources({'output': []})
