import os
import keyring


class CredentialStore:
    ENV = {'openai': 'OPENAI_API_KEY', 'elevenlabs': 'ELEVENLABS_API_KEY'}

    def get(self, provider):
        if provider not in self.ENV:
            raise ValueError('Unknown provider.')
        value = os.environ.get(self.ENV[provider])
        if value:
            return value
        try:
            return keyring.get_password('Katsu Studio', provider)
        except keyring.errors.KeyringError:
            return None

    def set(self, provider, value):
        if provider not in self.ENV:
            raise ValueError('Unknown provider.')
        if len(value.strip()) < 10:
            raise ValueError('Enter a valid API key.')
        try:
            keyring.set_password('Katsu Studio', provider, value.strip())
        except keyring.errors.KeyringError:
            raise ValueError('Keychain is unavailable. Set the provider environment variable before launching.') from None

    def status(self):
        return {name: bool(self.get(name)) for name in self.ENV}
