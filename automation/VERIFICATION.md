# Verification — October 3, 2026

## Automatic illustration planning

Users now choose target minutes without an illustration-count control in New video or Settings. New projects start with no planned count. Writing follows the chosen duration and words-per-minute estimate; the scene planner chooses images from the completed canonical narration, grouping related paragraphs and covering every character exactly once. The resulting scene count is shown before image generation. An internal 120-scene limit stops excessive plans before any image purchase.

The current complete local suite passes **88 Python/video tests**, including eight automatic-planning and upgrade regressions. **Six frontend submission-recovery tests** and the production React/TypeScript build pass. The actual OpenAI SDK parses synthetic writing/planning HTTP responses without a preset count; a real two-image FFmpeg fixture export uses the exact grouped narration and reuses saved paid results on repeat runs. Legacy scripts and scene fingerprints, old browser request bodies, omitted-count API retries, and historical re-import remain compatible. Independent review reports no unresolved findings after two upgrade fixes were reproduced as failing tests and corrected.

In-app-browser checks at 1360×960 and 390×844 verify absent count controls, editable target minutes, Settings defaults, a pending count on project/list views, and no horizontal overflow or console errors. A UI-created three-minute fixture stored 180 seconds and an automatic pending count with zero provider requests. Its database row and files were archived outside active projects. The original episode's complete stored payload and request count remain unchanged. Screenshots and the cleanup/check record are under `evidence/auto-scenes-*` and are excluded from Git.

No real OpenAI or ElevenLabs generation was run for this correction. Creative scene selection and actual generated length still need verification with the owner's configured accounts.

## Topic suggestions and artwork editing

The latest complete local suite passes **80 Python/video tests**. The frontend's **three edit-submission recovery tests** and production TypeScript/React build pass. GitHub's frontend check now runs those recovery tests as well as the build.

Live public feed checks verified ScienceDaily mind/brain, Smithsonian history and science/nature, and NASA. The browser showed five suggestions from three publishers, then ten after **View more**; selecting a suggestion filled and focused the editable topic field without creating a project. Twenty-three topic regressions cover parsing, deduplication, varied publishers, caching/restart, partial and total outages, bounded fetches and pagination. A cache-refresh regression failed before exclusion-based pagination was added; **View more** now returns unseen ideas even after refresh.

Eleven artwork regressions exercise real persistence and FFmpeg exports with only paid provider boundaries replaced. They cover upload previews, stale-draft protection, version restoration, preservation of complete thumbnail composition, exact JPEG dimensions/size, narration and other-image reuse, retained exports, paid edit idempotency, uncertain outcomes, cancellation recovery without keys, and replacing a stopped saved export with a normal production action. The actual OpenAI SDK also passes a synthetic HTTP multipart test proving that an edit sends the current composed image; a timeout makes exactly one request.

Using the in-app browser, a temporary four-scene episode passed scene upload → preview → save → checked video rebuild → original-version restore, plus thumbnail upload → preview → save without a video rebuild. No artwork API requests were made. The fixture's files and database rows were archived outside the active app; only the original episode remains, with its complete project payload and request count unchanged.

Desktop (1360 × 960) and mobile (390 × 844) topic and thumbnail-editor views have no horizontal overflow. Thumbnail previews decode and the inspected browser reports no console errors. Final screenshots and the cleanup record are local under `evidence/topics-final-*.jpg`, `editor-final-*.jpg`, `editor-preview-desktop.jpg` and `ui-test-record.json`; they are excluded from the public repository.

Independent review found and verified fixes for paused-job mode conflicts, feed-refresh pagination, browser edit retry identity, settled-preview recovery without keys, and legacy actions replacing a stopped saved export. The final review reports no remaining critical or important findings. Paid edits against the owner's real OpenAI account, visual fidelity and actual billing remain unverified until a key is supplied; uploads and local exports are verified independently.

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

To complete that verification, enter keys privately in Settings, load and save a voice, check connections, then create a one-minute project with illustrations planned from its script within the configured estimate limit. A model-list check alone does not prove image editing, speech generation or complete end-to-end production.

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
