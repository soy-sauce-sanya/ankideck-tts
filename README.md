
# AnkiDeck TTS (queue version)

English UI, queue per-row progress, sequential processing.

## API key setup

Set provider keys in Anki via:
`Tools -> Add-ons -> AnkiDeck TTS -> Config`

Supported keys:
- `tts.api_key` (global fallback)
- `tts.api_keys.dashscope`
- `tts.api_keys.openai`
- `tts.api_keys.elevenlabs`
- `tts.api_keys.gemini`

Gemini TTS uses the Google Gemini API with preview TTS models and saves audio as `.wav`.

## GitHub Pages

GitHub Pages files and deployment workflow are maintained in the `webpage` branch.
