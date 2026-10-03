# Katsu Studio

A local FastAPI + React application for **Katsu The Printer**. Enter a topic to automatically research, write, plan scenes, generate original still illustrations and timed narration, shorten pauses, match illustrations to words, export a checked 1080p MP4, and generate its thumbnail.

## Open the studio

Double-click `run.command` in Finder, or run `./automation/run.command` from the project folder. It opens **http://127.0.0.1:8850** and keeps production in the local terminal. Leave that terminal open while a video is producing. The first launch creates a private Python environment and installs backend dependencies; if the frontend build is missing, it builds it too.

Prerequisites: Python 3.12, Node.js 22 and FFmpeg (`brew install python@3.12 node ffmpeg`). The current Mac already has these. Keep this folder alongside `compose_video.py` and `remove_reader_pauses.py`; the application reuses those proven tools without changing them.

## One-time setup

1. Open **Settings**. Paste your OpenAI and ElevenLabs API keys into the private password fields and save each. Do not paste keys into chat.
2. Click **Load voices**, select the narrator, and **Save preferences**. Hannibal's voice ID is selected from your actual account; it is never guessed.
3. Check model names and **Check connections**. Defaults are configurable: `gpt-6-astra` for writing/research, `gpt-image-1.5` for reference-guided images, and `eleven_multilingual_v2` for narration. Access depends on your accounts. A connection check verifies credentials/listed resources; actual generation is a separate check.
4. Set an estimated spending limit and review the price inputs under **Models, estimates, and timing**. Default figures are conservative planning inputs, not current billing quotes. For a first provider test, choose a one-minute topic and four illustrations.

ChatGPT subscriptions and OpenAI API billing are separate. ElevenLabs API requests use its own account plan/credits. This app sends the topic, research context, narration, style and character reference to the relevant providers. Secrets remain in macOS Keychain, or server environment variables `OPENAI_API_KEY` and `ELEVENLABS_API_KEY`. They are never returned to the UI or saved in project exports. Environment variables take precedence over Keychain; replacing a Keychain value does not override an existing environment variable.

## Produce a video

Enter a question in **New video**, choose the length and illustration count, and click **Make my video**. Production proceeds automatically after setup. No routine script or sample-image approval stops. Follow the eight stages, or return later. The completed episode contains a video player, download, full narration, a gallery showing each image with its exact voiceover, a thumbnail preview and download, and research references.

**Thumbnail** is the last stage. OpenAI chooses a truthful two-to-six-word headline from the finished story and creates reference-guided Katsu artwork. The app adds exact, readable lettering locally using the bundled, SIL Open Font License Fredoka font. It exports a 3840 × 2160 JPEG under 2 MB, matching [YouTube's current recommendations](https://support.google.com/youtube/answer/72431?hl=en). The output canvas is 4K; generated artwork is resized to fit it. Thumbnail planning and artwork use the same estimated spending limit and saved-response recovery as the video.

Completed exports also offer script data, the timing report, and **Download images & scene wording** (a ZIP containing all registered illustrations plus matching `scenes.json`). Preparing that ZIP also makes a plain narration text download available.

The eight-minute default is a script target. **Actual recorded duration controls the final video.** Speech is never silently sped up to fit a target. Images remain still with direct cuts and optional static labels. No animation or publishing.

**Bring in our first video** imports the existing 9:28 episode once, including 120 illustrations and its reviewed word timing. This optional owner-only action requires the original local episode files, which are excluded from the public repository. Imports copy into local project storage; original source files remain untouched. Historical imports have no automatic research record and no API costs attributed to them. New-topic production includes a bundled Katsu avatar and character reference and needs no historical episode files.

The original episode now also has a **NEVER ENOUGH?** thumbnail. Its artwork was made with Codex's built-in image tool using our approved character reference, then finished with the app's lettering renderer. It is a real example, separate from an unverified Studio API run. It stays saved until you explicitly request a new thumbnail.

## Changes and recovery

- Edit a scene's visual or request **New image** to replace that illustration and invalidate the export. The recording stays reusable.
- Edit exact voiceover wording to invalidate narration, word timing, export and thumbnail. Other illustrations remain reusable. Owner edits are preserved when production continues.
- **New thumbnail** regenerates its concept and artwork without researching, rewriting, recording or rendering the video again. Finished episodes without a thumbnail offer **Make thumbnail**. These actions use your current saved OpenAI models and spending limit.
- If thumbnail production stops, the completed video stays available. **Continue production** resumes only the thumbnail using current OpenAI preferences; successful requests remain reusable. A voice connection is unnecessary for this retry.
- **Continue production** applies current saved provider/voice preferences and spending limit to that stopped project, keeping its original target duration and scene count. Relevant caches are checked against content, models, style and reference hashes.
- **Stop production** prevents new requests. Already running requests finish and their successful assets are retained. Stop is not a provider refund or immediate termination of local FFmpeg.
- Restarting leaves interrupted projects in **Needs attention**. Resume reconciles persisted successful results and reuses matching saved versions, including versions from restored settings. Requests with uncertain outcomes are never replayed automatically. Inspect request records, saved responses in the project folder, and provider history/billing. Explicitly allow another paid attempt only if desired; the previous estimate remains counted.
- A timeout or malformed paid response may require inspection. Known request rejection can be retried safely. The application uses zero automatic paid retries; user-triggered resume is bounded by persisted reservations and the project estimate limit.

The spending limit gates **estimates before each request**, not the provider's final bill. Actual usage is recorded when returned; conservative reservations remain counted. It cannot guarantee an exact account spending cap.

## Files and privacy

`data/studio.sqlite` stores settings, projects, registered artifacts and request state. `data/channel/` stores the channel reference/style. `data/projects/<id>/` contains versioned scripts, images, original voice chunks, joined/edited audio, word timing, render cache and exports. Successful assets and paid responses are retained. The service binds only to loopback and rejects foreign browser origins/hosts.

Back up `data/` to preserve projects. To free render-cache space, stop the server first, then remove only `data/projects/<id>/render-cache/`; the exported MP4 and original illustrations remain. There is no automatic deletion of project assets. Never delete the database while keeping projects and expecting automatic recovery.

Character alignment is preferred for exact timing. If a provider returns missing or invalid alignment, optional local Whisper can transcribe the actual joined audio: install `openai-whisper` into `.venv`. Without it, the app gives an actionable error rather than inventing timing. No background transcription model download is needed for valid ElevenLabs alignment.

## Development and verification

Backend: `.venv/bin/python -m pip install -e './backend[test]'` then `.venv/bin/python -m pytest backend/tests -q` from `automation/`.

Separate developer servers: `.venv/bin/python -m uvicorn katsu.main:create_app --factory --host 127.0.0.1 --port 8850` and `npm run dev` from `frontend/`. Production: `npm run build`, then run the backend to serve that build.

Read `VERIFICATION.md` for actual evidence and the remaining real-provider check. Test fixtures replace only paid provider boundaries; they are never offered as production generation.

Provider references used during implementation: [OpenAI image generation](https://developers.openai.com/api/docs/guides/image-generation), [Responses web search](https://developers.openai.com/api/docs/guides/tools-web-search), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), and [ElevenLabs speech with timestamps](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps).
