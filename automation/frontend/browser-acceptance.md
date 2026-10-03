# Browser acceptance

Use the actual React build and local FastAPI app. No mock service in the production UI.

- The existing completed episode appears once after import; preview plays with sound, measured duration and 120 scenes. Download resolves to a real MP4.
- Settings show missing credentials clearly, never key values. Save preferences, reload, and confirm persistence. Voice list errors explain setup.
- Topic creation uses one idempotency key, disables repeated clicks, navigates to persisted progress. Missing keys produce actionable attention, with no paid requests.
- A fixture job through the real worker exposes its measured runtime and verified export; its title identifies synthetic test material. Production never substitutes fixtures for providers.
- Narration and image tabs show exact stored scene wording and registered images. Edit visual removes only that image/export; edit wording also invalidates narration/timing. Active work disables editing.
- Resume, cancel, failure recovery and paid-outcome acknowledgement use explicit API routes and refresh current state.
- Desktop and 390px layouts have readable controls, keyboard focus, labels, accessible status/errors and no horizontal overflow.
