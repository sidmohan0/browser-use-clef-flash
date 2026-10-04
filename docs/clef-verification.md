# Clef-Flash verification — October 4, 2026

The fork calls Cloudflare-hosted `@cf/cloudflare/clef-flash` directly. A token restricted to one account with Workers AI: Read successfully performed inference. No Worker deployment, plan upgrade, or model download was needed. Credentials are stored only in the local ignored `.env` with mode 0600.

## Actual REST boundary

A live request used the account-scoped `/ai/run/@cf/cloudflare/clef-flash` URL, bearer authentication, JSON content type, and `model: "clef-flash"`, with the existing structured `state` and `questions`. The response had `success: true`, empty `errors`/`messages`, and this model result:

```json
{
  "model": "clef-flash",
  "answers": {
    "operation": {
      "type": "choice", "choice": "CLICK",
      "probabilities": {"CLICK": 0.8653, "DONE": 0.0694, "BLOCKED": 0.0653},
      "confidence": 0.6367
    },
    "click_target": {
      "type": "choice", "choice": "1",
      "probabilities": {"1": 0.9858, "2": 0.0142}, "confidence": 0.9442
    }
  },
  "usage": {"input_tokens": 843, "output_tokens": 0}
}
```

`choose` normalized this envelope, validated both heads, and returned the observed action `e1`. Its request/body and response are recorded locally in ignored `artifacts/clef/live-boundary.json`; the authorization value is redacted.

The first probe with one target was rejected with HTTP 422: `Dictionary should have at least 2 items after validation, not 1`. Therefore singleton target questions are omitted. Once Clef chooses the operation, its sole observed target is passed through the existing validator. A target probability/confidence of 1.0 for this case is deterministic, not a model estimate. Actual model answers remain unchanged in `raw_answers`.

## Live browser outcome

Command: `uv run --env-file .env python scripts/smoke_navigation.py`.

Environment: macOS, Python 3.13.14, a dedicated headless Google Chrome profile, Browser Harness 0.1.13, and the upstream local reading-room fixture. Browser Harness connected through `BU_CDP_URL`; the user's normal browser profile was not used for this run.

Goal: open “A browser is a choice, not a conversation.” The run completed with two live Clef decisions, one executed click, and zero text-helper calls. A fresh browser read independently checked:

- Final URL exactly matched the fixture URL with `#choices`.
- Final document title matched the requested article.
- Article body contained “Freshness is part of correctness.”
- Execution history contained a click.

Observed loop time was 879 ms for this single local-fixture run, excluding browser setup and initial observation. This is not a benchmark or a comparison with upstream performance. Full local evidence is in ignored `artifacts/clef/navigation.json`.

## Checks and limits

- 50 offline tests passed, including HTTP/auth/request shape, REST envelope normalization, failure before browser execution, choice validation, singleton target handling, and configurable text-helper parsing.
- 21 real-browser guard checks passed via `scripts/check_guards.py`, with no model calls.
- Ruff, both JavaScript syntax checks, `git diff --check`, and `uv build` passed.
- MIT license and original copyright were retained.

Live `TYPE_TEXT` has not been verified: the local `TEXT_MODEL_API_KEY` is blank. Set a text-provider key to run the existing typing examples. The example configuration retains OpenRouter Mercury 2.5 with reasoning disabled. No text values were hardcoded to bypass this helper.

Historical videos and performance documents belong to the upstream TypeSafe/Jev implementation. They are not evidence of Clef latency or reliability.
