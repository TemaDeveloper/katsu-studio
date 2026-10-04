import pytest
import httpx
from katsu.models import StudioSettings
from katsu.providers.elevenlabs import ElevenLabsProvider
from katsu.providers.openai import OpenAIProvider, decode_image, extract_sources
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


def test_image_edit_sends_current_composed_image_through_real_sdk(tmp_path):
    import base64
    from io import BytesIO
    from PIL import Image
    from openai import OpenAI
    current = tmp_path / 'current.jpg'
    Image.new('RGB', (1280, 720), 'red').save(current)
    output = BytesIO()
    Image.new('RGB', (1536, 1024), 'blue').save(output, 'PNG')
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.path == '/v1/images/edits'
        body = request.read()
        assert current.read_bytes() in body
        assert b'Make the headline bigger' in body
        assert b'preserve the existing' in body
        return httpx.Response(200, json={'created': 1, 'data': [{'b64_json': base64.b64encode(output.getvalue()).decode()}]}, headers={'x-request-id':'edit-proof'})
    sdk = OpenAI(api_key='fixture-key', max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    provider = OpenAIProvider('fixture-key', StudioSettings(), client=sdk)
    dest = tmp_path / 'preview.png'
    provider.edit_image('Make the headline bigger', current, dest)
    assert len(calls) == 1
    assert dest.with_suffix('.response.json').is_file()
    with Image.open(dest) as image:
        assert image.size == (1536, 1024)
    assert provider.last_metadata['request_id'] == 'edit-proof'


def test_image_edit_transport_timeout_does_not_retry(tmp_path):
    from PIL import Image
    from openai import OpenAI
    current = tmp_path / 'current.png'
    Image.new('RGB', (640, 640), 'red').save(current)
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout('fixture timeout')
    sdk = OpenAI(api_key='fixture-key', max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    provider = OpenAIProvider('fixture-key', StudioSettings(), client=sdk)
    with pytest.raises(UnknownOutcome):
        provider.edit_image('Bigger eyes', current, tmp_path / 'preview.png')
    assert len(calls) == 1
