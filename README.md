
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

## Provider catalogs

Use the `↻` button next to Provider to refresh available models and voices. Catalogs are cached for 24 hours and fall back to the bundled lists when offline. Model and Voice fields also accept IDs entered manually.

ElevenLabs refreshes both account voices and TTS models. OpenAI and Gemini refresh compatible TTS models; their built-in voice lists remain bundled. DashScope currently uses its bundled system catalog.

## GitHub Pages

GitHub Pages files and deployment workflow are maintained in the `webpage` branch.
