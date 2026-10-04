
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
- `tts.api_keys.local` (optional, only if your local TTS server requires one)

The legacy single `tts.api_key` is only used by old configs that have no per-provider keys, and is removed once a key is saved from the panel.

DashScope (Qwen TTS) is called over its REST API directly, so no extra Python package is required. The default endpoint is `https://dashscope.aliyuncs.com` (mainland China accounts); for international accounts set `tts.dashscope_base_url` to `https://dashscope-intl.aliyuncs.com`.

Gemini TTS uses the Google Gemini API with preview TTS models and saves audio as `.wav`.

## Local TTS server

Choose **Local TTS server** as the provider to use any server with an OpenAI-compatible `/v1/audio/speech` endpoint. No API key is needed; the API key field becomes **Server URL** (default `http://localhost:8000/v1`). A bare `host:port` is accepted and `/v1` is added automatically.

On Apple Silicon Macs, [mlx-audio](https://github.com/Blaizzy/mlx-audio) runs natively on the GPU:

```bash
python3 -m venv ~/mlx-audio-env
source ~/mlx-audio-env/bin/activate
pip install "mlx-audio[server,tts]"
mlx_audio.server --port 8000
```

Models are downloaded on first use, so the first request is slow. Examples:

| Model | Voices |
|---|---|
| `mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit` | `Vivian`, `Serena`, `Uncle_Fu`, `Dylan`, `Eric` (Chinese), `Ryan`, `Aiden` (English), `Ono_Anna`, `Sohee`; detects the text language itself |
| `mlx-community/Kokoro-82M-bf16` | `af_heart`, `af_bella`, … (English) |

Other servers work too, e.g. [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) in Docker (`http://localhost:8880`). LM Studio and Ollama do not synthesize speech themselves, so they cannot be used directly.

The add-on sends `model`, `input`, `voice` (if set) and `response_format` (default `wav`, see `tts.exts.local`). Local requests bypass system proxies and time out after 5 minutes. Models are listed from `<Server URL>/models` and voices from `<Server URL>/audio/voices` when the server provides them; both fields also accept any ID typed manually. If the server needs a key, set `tts.api_keys.local`.

Settings saved for the former **LM Studio (local)** / **Ollama (local)** providers are moved to **Local TTS server** automatically.

## Provider catalogs

Use the `↻` button next to Provider to refresh available models and voices. Catalogs are cached for 24 hours and fall back to the bundled lists when offline. Model and Voice fields also accept IDs entered manually.

ElevenLabs refreshes both account voices and TTS models. OpenAI and Gemini refresh compatible TTS models; their built-in voice lists remain bundled. DashScope currently uses its bundled system catalog.

## GitHub Pages

GitHub Pages files and deployment workflow are maintained in the `webpage` branch.
