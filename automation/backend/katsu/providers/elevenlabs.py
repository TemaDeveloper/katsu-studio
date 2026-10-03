import base64
from pathlib import Path
import httpx
import json
import subprocess
from .errors import ProviderError, UnknownOutcome


class ElevenLabsProvider:
    def __init__(self, key, settings, client=None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=httpx.Timeout(240, connect=15))
        self.key = key
        self.last_metadata = {}

    def _request(self, method, path, **kwargs):
        try:
            response = self.client.request(method, 'https://api.elevenlabs.io/v1/' + path, headers={'xi-api-key': self.key}, **kwargs)
        except httpx.TransportError:
            if method == 'POST':
                raise UnknownOutcome('ElevenLabs timed out or disconnected. This request may have been billed; check its outcome before retrying.') from None
            raise ProviderError('ElevenLabs connection failed. Check your connection and API key.') from None
        if response.status_code >= 500 and method == 'POST':
            raise UnknownOutcome('ElevenLabs could not confirm the paid request outcome. Check billing before retrying.')
        if not response.is_success:
            raise ProviderError(f'ElevenLabs rejected the request (HTTP {response.status_code}). Check the voice, key, model and billing in Settings.')
        self.last_metadata = {'request_id': response.headers.get('request-id') or response.headers.get('x-request-id')}
        return response

    def list_voices(self):
        data = self._request('GET', 'voices').json()
        return [{'id': v['voice_id'], 'name': v['name']} for v in data.get('voices', [])]

    def generate_speech(self, text, destination: Path, previous_text='', next_text=''):
        if not self.settings.voice_id:
            raise ProviderError('Choose your ElevenLabs voice in Settings before creating a video.')
        payload = {'text': text, 'model_id': self.settings.voice_model, 'voice_settings': {
            'stability': self.settings.voice_stability, 'similarity_boost': self.settings.voice_similarity,
            'speed': self.settings.voice_speed}, 'previous_text': previous_text[-1000:] or None, 'next_text': next_text[:1000] or None}
        response = self._request('POST', f'text-to-speech/{self.settings.voice_id}/with-timestamps', params={'output_format': 'mp3_44100_128'}, json=payload)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.with_suffix('.response.json').write_text(response.text)
        try:
            data = response.json()
            raw = base64.b64decode(data['audio_base64'], validate=True)
            temp = destination.with_suffix('.part.mp3')
            temp.write_bytes(raw)
            result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(temp), '-f', 'null', '-'], capture_output=True)
            if result.returncode or len(raw) < 100:
                raise ValueError('Invalid audio')
            temp.replace(destination)
            data.pop('audio_base64')
        except Exception:
            raise ProviderError('ElevenLabs returned unusable audio. The paid response is retained for inspection.') from None
        data.update(path=str(destination), text=text, **self.last_metadata)
        return data
