
# AnkiDeck TTS (queue version)

English UI, queue per-row progress, sequential processing.

## API key setup

Set provider keys in Anki via:
`Tools -> Add-ons -> AnkiDeck TTS -> Config`

Each provider has its own key; a provider without a key never borrows another provider's key.

Supported keys:
- `tts.api_keys.dashscope`
- `tts.api_keys.openai`
- `tts.api_keys.elevenlabs`
- `tts.api_keys.gemini`
- `tts.api_keys.lmstudio`, `tts.api_keys.ollama` (optional, only if your local server requires one)

The legacy single `tts.api_key` is only used by old configs that have no per-provider keys, and is removed once a key is saved from the panel.

DashScope (Qwen TTS) is called over its REST API directly, so no extra Python package is required. The default endpoint is `https://dashscope.aliyuncs.com` (mainland China accounts); for international accounts set `tts.dashscope_base_url` to `https://dashscope-intl.aliyuncs.com`.

Gemini TTS uses the Google Gemini API with preview TTS models and saves audio as `.wav`.

## Local models (LM Studio / Ollama)

Choose **LM Studio (local)** or **Ollama (local)** as the provider. No API key is needed; the API key field becomes **Server URL** (defaults: `http://localhost:1234/v1` for LM Studio, `http://localhost:11434/v1` for Ollama). A bare `host:port` is accepted and `/v1` is added automatically.

The add-on sends OpenAI-compatible requests to `<Server URL>/audio/speech` with `model`, `input`, `voice` (if set) and `response_format` (default `wav`, see `tts.exts`). Local requests bypass system proxies and time out after 5 minutes.

LM Studio and Ollama do not synthesize speech on their own, so the server at this URL must expose `/v1/audio/speech` — for example a TTS bridge such as Orpheus-FastAPI (which can use a model loaded in LM Studio or Ollama as its backend) or Kokoro-FastAPI. If the endpoint is missing, the queue shows a "no /audio/speech endpoint" error.

Models are listed from `<Server URL>/models` each time the provider is selected (or on `↻`); voices from `<Server URL>/audio/voices` when the server provides it. Both fields also accept any ID typed manually. If the server needs a key, set `tts.api_keys.lmstudio` / `tts.api_keys.ollama` in the add-on config.

## Provider catalogs

Use the `↻` button next to Provider to refresh available models and voices. Catalogs are cached for 24 hours and fall back to the bundled lists when offline. Model and Voice fields also accept IDs entered manually.

ElevenLabs refreshes both account voices and TTS models. OpenAI and Gemini refresh compatible TTS models; their built-in voice lists remain bundled. DashScope currently uses its bundled system catalog.

## GitHub Pages

GitHub Pages files and deployment workflow are maintained in the `webpage` branch.
