# Verification — October 3, 2026

## Verified

- Dedicated Python 3.12 environment: dependencies installed; `pip check` reports no broken requirements.
- Backend: **36 tests pass** (27.35 seconds after the thumbnail addition), including real FFmpeg fixture exports, a real background-worker run, settings/persistence, idempotency, local-origin and file containment, source/scene validation, provider transport fixtures, budgets, cancellation/resume and selective edit invalidation.
- Production React/TypeScript build passes. FastAPI serves that build on loopback.
- Existing completed episode imports once, preserving original video hash. It previews with the original 9:28 narration and 120 image/wording pairs. This is a historical import, not a new AI-generated episode.

## Browser evidence

Acceptance script `frontend/verify-browser.cjs` passed against the running app in real Chrome: imported episode playback advances, all 120 scenes have exact wording, settings persist, missing credentials stop production with zero committed estimates, and resume shows actionable feedback. Desktop (1360×960) and mobile (390×844) have no horizontal overflow or JavaScript page errors.

`frontend/verify-review.cjs` passed uncertain-POST recovery across refresh: the same persisted submission identity returns the same project, with no duplicate creation. `frontend/verify-stale-poll.cjs` passed a real scene edit while an older completed-project response was held; releasing that response cannot restore the invalidated export. That regression failed when the response guard was deliberately removed and passed when restored.

`frontend/verify-accessibility.cjs` passed visible keyboard focus, ArrowRight tab selection and field boundary contrast. Arrow/Home/End tab handling and reduced-motion rules are implemented. This is targeted accessibility evidence, not a full assistive-technology audit.

`frontend/verify-final-screens.cjs` captured final clean desktop/mobile viewports, decoded gallery images and settings voice controls. It confirmed that the self-hosted Fredoka display font is actually loaded. Only the original completed episode remains in the app; generated acceptance projects were removed after verification. Cleanup IDs are recorded in `evidence/test-project-cleanup.json`.

Machine-readable evidence, full test results and screenshots are under `evidence/`. The launcher passes its syntax check; the actual FastAPI server serves the production React build on loopback.

## Real-provider boundary

No OpenAI or ElevenLabs credentials are configured in Studio. No paid Studio provider requests were run. Research, structured writing, reference-guided images, thumbnail concept/artwork, voice listing and speech-with-timestamps adapters exist and are tested at transport/fixture boundaries. Their behavior with this owner's real accounts, voices, models and billing is **unverified**. The first thumbnail was separately generated with Codex's built-in image tool; it does not prove the Studio API connection.

To complete that verification, enter keys privately in Settings, load and save a voice, check connections, then create a one-minute/four-illustration project within the configured estimate limit. A model-list check alone does not prove image editing, speech generation or complete end-to-end production.

The fully automatic orchestration and local video assembly are verified with synthetic provider fixtures. Production never falls back to those fixtures.

## Review

Independent fresh code review found no Critical issues and four Important recovery/idempotency issues. Two additional findings about promised downloads and stale polling were treated as material. All six were addressed: paid results persist before registration, older artifact versions recover when settings are restored, manual scene edits preserve their canonical script, uncertain submission identity survives refresh, script/image/timing downloads are present, and obsolete polls are discarded. Targeted regressions demonstrated failures, then passed; the complete backend suite remains green.

Independent visual review requested four material fixes: topic-field focus, tab keyboard behavior, field border contrast and a persistent display font. The final reviewer scored all four **resolved**, with disposition **ship**, after inspecting the twelve final captures. The verdict is recorded in `evidence/visual-review.md`.

The documenter recorded the actual built system in `DESIGN.md` and `.impeccable/design.json`: canonical sections, source colors, final font/field overrides, token references and seven self-contained component previews validated. No implementation files changed during that pass.

Deferred minor polish: pending project previews still use a play symbol; production changes and connection-check results lack live announcements. Ordinary status/error text remains visible. Logo tracking was corrected as part of the display-font change.

## Thumbnail addition

Automatic production now completes with a thumbnail. Six focused backend regressions verify downloadable 3840 × 2160 JPEG output below 2 MB, repeat-run reuse, uncertain-request protection, separate regeneration, spending-limit recovery with the video intact, current thumbnail model preferences without rebuilding the episode, wording invalidation, and structured concept parsing/refusal through the actual OpenAI SDK with synthetic HTTP transport.

`frontend/verify-thumbnail.cjs` passed in real Chrome. The original episode's preview decodes at 3840 × 2160, its download is exactly 440,438 bytes, the episode cover uses it, and video playback still advances. Five-tab keyboard navigation works. Desktop (1360 × 960) and mobile (390 × 844) show no horizontal overflow or page errors. Requesting a new thumbnail on a synthetic episode without credentials leaves the video and audio fingerprints intact, adds no spending reservations, and exposes actionable Settings/Continue controls. The test-only episode was removed; only the original episode remains. Evidence is in `evidence/thumbnail-browser-verification.json`, `thumbnail-fixture-cleanup.json`, and `thumbnail-*.png`.

The first episode's **NEVER ENOUGH?** artwork was generated with the built-in Codex image tool using the approved original character reference, then composed by the same local headline renderer used in production. It is registered as `codex_artwork`, identified in the UI, and preserved until explicit regeneration. Its source and dimensions are recorded in `evidence/first-thumbnail.json`. Original video, recording and illustrations remain preserved.

## Public repository checkout

The public source includes the avatar and character reference as backend package assets. New channel initialization falls back to those assets when the owner's original `output/` folder is absent, while preserving any existing saved channel assets. A startup regression first failed on the missing avatar, then passed after bundling the assets.

A clean exported source tree with a separate Python environment and freshly installed frontend dependencies passed **42 tests, with two owner-only historical tests skipped**, in 33.08 seconds. Its production frontend build and dependency check passed. A fresh empty-data app served its health, settings, project list, avatar and UI successfully; the reference image decoded. Optional historical import correctly reported unavailable source files.

Git ignores project data, generated media, owner-only episode documents, environment files, dependencies and local evidence. Staged source was checked for credential patterns and personal machine paths. The browser-check scripts now resolve installed Playwright or an explicit `KATSU_PLAYWRIGHT_PATH`, rather than a particular user's runtime path. GitHub checks run the offline Python/video suite and React production build. Local evidence files referenced above are intentionally not published.
