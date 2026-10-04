# Cloudflare Flights recording — October 4, 2026

The verified configuration uses `CLEF_MODEL=clef` (Cloudflare’s 27B decision model) and `TEXT_MODEL=@cf/openai/gpt-oss-20b` with low reasoning. Both inference paths use the existing account-scoped Workers AI: Read token. Clef is now the repository default based on this run; Clef-Flash remains available via `CLEF_MODEL=clef-flash`.

## Result

Task: find one-way flights from Zurich to London on November 20, 2026, for one adult in economy; stop at matching results without selecting or booking a flight.

The recorded run took 30,448 ms from the first prediction through the final DONE decision, excluding browser startup and initial observation. It used 25 decisions, 18 executed actions, and two text-helper calls (Zurich and London). The test used an isolated headless Chrome profile on macOS with Browser Harness 0.1.13. The GIF/MP4 shows the complete recorded interval at 1× with a one-second final hold. This single success is not a reliability or speed benchmark.

The recorder took a fresh final browser observation. Independent checks verified Google's flight-search URL, one-way selection, Zürich/ZRH origin, London destination, November 20, 2026, one passenger, economy cabin, and matching visible flight options. No flight was selected or booked.

The inherited verifier initially rejected the accessible origin label “Where from? Zürich ZRH” because it expected exactly “Where from?”. The value was “Zürich”, the encoded URL contained ZRH, and the visible flights departed Zurich Airport. The revised verifier accepts the field’s airport suffix while still checking the value, and now also checks passengers and cabin. Rechecking the original fresh final observation passed all nine checks. The original raw record is preserved; its reviewed verification is stored separately.

## Failures and targeted changes

1. Llama 3.1 8B FP8 passed the origin probe but answered a destination probe incorrectly. It was not selected as the final helper. GPT-OSS 20B answered correctly and generated both field values in the recorded run.
2. Two Clef-Flash runs selected multi-airport controls and became stuck. Text-only instruction/option representations did not fix the saved decision. Adding the goal directly to the shared state corrected the saved origin suggestion choice, with a regression assertion for the request content. This is an observed improvement, not proof of general model reliability.
3. A further Clef-Flash run filled both cities but repeatedly chose WAIT at London’s suggestions until reaching the existing 60-action budget.
4. The larger Clef model chose sensible targets on both saved picker states. The next live run completed the search. Only the model selector and goal-in-state change were needed; no site-specific action plan, hardcoded field values, or browser-guard bypass was added.

Local raw evidence remains ignored under `artifacts/flights/cloudflare-01` through `cloudflare-04`. The successful run includes original screencast timestamps, model requests/answers, source hashes, history, and fresh final page data. Raw evidence contains no bearer token. Published media omits Google's account-control strip; the profile was signed out.

## Reproduction

Set Cloudflare account ID/token and `CLEF_MODEL=clef` in `.env`, leaving the default GPT-OSS text settings. Connect Browser Harness, then:

```bash
uv run --env-file .env python scripts/record_flights.py artifacts/flights/new-run
uv run python scripts/render_recording.py artifacts/flights/new-run --output artifacts/flights/video
```

The renderer independently rechecks final page data and refuses an unverified run. The historical upstream GIF/MP4 are retained separately.

## Sources

- [Cloudflare GPT-OSS 20B](https://developers.cloudflare.com/workers-ai/models/gpt-oss-20b/)
- [Cloudflare Clef](https://developers.cloudflare.com/workers-ai/models/clef/)
- [Cloudflare OpenAI-compatible endpoints](https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/)
