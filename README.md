# Browser Use Clef-Flash

An independent adaptation of [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) using [Cloudflare-hosted Clef-Flash](https://developers.cloudflare.com/workers-ai/models/clef-flash/) for browser decisions. This fork is not maintained or endorsed by Cloudflare or Browser Use. Package and CLI names remain `jev_ultrafast` and `jev`.

**A browser agent with a dynamic, indexed action space.**

Give it one goal. Clef-Flash picks an operation and an element. A small LLM writes text only when the operation is `TYPE_TEXT`.

**Upstream demonstration (TypeSafe/Jev, not a Clef measurement):** Zürich → London on Google Flights in 7.1 seconds. The video and historical performance documents below are retained as upstream evidence only.

<a href="docs/demo.mp4"><img src="docs/demo.gif" alt="A real Google Flights search at 1× speed, with generated city names and dynamic operation/target decisions" width="100%" /></a>

[Watch the MP4](docs/demo.mp4) · [Measurements](docs/performance.md) · [Read the loop](jev_ultrafast/agent.py)

## The action space

Every observation produces a new element table:

```text
[1] button    Change ticket type · Round trip
[2] combobox  Where from?        · San Francisco
[3] combobox  Where to?          · empty
[4] textbox   Departure          · empty
...
```

The operations are `CLICK`, `TYPE_TEXT`, `SELECT`, `SCROLL_UP`, `SCROLL_DOWN`, `WAIT`, `DONE`, and `BLOCKED`. Only supported operations and targets are offered.

```text
                      one Clef-Flash request
                     ┌───────────────────────────┐
page → element table → operation                 │
                     │ click_target              │
                     │ type_text_target          │
                     │ select_target, if present │
                     └─────────────┬─────────────┘
                         use the matching target
                                   │
                    CLICK [7] ─────┤──→ browser
                TYPE_TEXT [3] ─────┘
                          ↓
                   small LLM → text → browser
```

Target questions are speculative. If the operation is `CLICK`, only `click_target` can execute. Two decisions, **one network round trip**. Each target head contains only compatible elements. Clef requires at least two choices per question: when an operation has exactly one observed target, that target is determined locally after Clef selects the operation and still passes the existing validator and browser guards. Its reported target probability/confidence is deterministic (1.0), not a model estimate. Native dropdown choices carry an observed element/option index.

There are no site-specific action scripts or prepared field strings in the policy. The Flights example supplies a goal and independently verifies the outcome. The screenshot renderer adds labels afterward; it does not drive the browser.

## Try it

```bash
git clone https://github.com/sidmohan0/browser-use-clef-flash.git
cd browser-use-clef-flash
uv sync
cp .env.example .env
# Add CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, and TEXT_MODEL_API_KEY.
uv run jev
```

Open **http://127.0.0.1:8766** and click **Start demo → Run automatically**. The inspector shows numbered elements, operation probabilities, target probabilities, and executed actions. **Choose next** pauses before execution.

Chrome connects through [Browser Harness](https://github.com/browser-use/browser-harness), installed by `uv sync`. Run `uv run browser-harness --doctor` if it needs connecting. Allow remote debugging in Chrome when prompted.

`TEXT_MODEL_API_KEY` is an OpenRouter key in the example configuration. The example defaults to `inception/mercury-2.5` with reasoning disabled. Keep `TEXT_MODEL`, `TEXT_MODEL_BASE_URL`, and `TEXT_MODEL_REASONING` configurable. Alternative providers must accept the helper’s chat-completion request, including JSON-object output and the chosen reasoning parameters; compatibility with every OpenAI-compatible endpoint has not been tested.

### Cloudflare access

In your Cloudflare account, create an API token with **Account → Workers AI → Read**, restricted to that account. Copy its account ID and token to the local ignored `.env`; never commit credentials. See the [REST API setup guide](https://developers.cloudflare.com/workers-ai/get-started/rest-api/). No Worker deployment or model download is required.

Decisions use `POST https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/cloudflare/clef-flash`, bearer authentication, and `model: "clef-flash"`. The decision path unwraps the REST `success`/`result` envelope and passes the model answers through the existing operation/target validator. Missing credentials, provider errors, and malformed or invalid decisions stop before browser execution. Text-helper response parsing, browser freshness guards, and retries remain unchanged.

Workers AI usage is subject to your account’s plan and [Cloudflare pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/). `TYPE_TEXT` also uses the configured text provider. A navigation-only task does not need a text key unless the model selects `TYPE_TEXT`.

## Use the library

```python
from jev_ultrafast import Agent

with Agent(
    "https://www.google.com/travel/flights?hl=en",
    "Find one-way flights from Zurich to London on September 20, 2026, "
    "for one adult in economy. Stop when matching flight options are visible.",
) as agent:
    for state in agent.run():
        print(state["elapsed_ms"], state["status"])
```

Run with `uv run --env-file .env python your_script.py`. The same policy can run a different task:

```bash
uv run --env-file .env python examples/run.py \
  --url https://en.wikipedia.org/wiki/Main_Page \
  --goal 'Find and open the Wikipedia article about Gödel’s incompleteness theorems.'
```

`uv run --env-file .env python examples/flights.py --keep-open` performs the flight search, checks the actual route/date/results, and saves its trace. It does not select or book a flight.

## Why it moves

- **One request per decision cycle.** Operation and target heads share the same observed state.
- **No screenshots in the default agent loop.** Clef-Flash consumes structured state. The inspector opts into screenshots; the video uses a separate continuous screencast.
- **One browser call per snapshot.** Read visible controls, their names, values, and text atomically. Keep references to the actual DOM nodes.
- **Validate the selected target.** Clicks check the document, form values, target, and nearby context. Animation alone does not force another prediction. Resolve current geometry and reject covered controls before input.
- **Wait for useful state.** After typing into a combobox, wait for visible suggestions, capped at 200 ms. Other interactions get at most two animation frames or 50 ms. These reads happen after execution is logged.
- **Keep hidden tabs rendering.** Focus emulation prevents background animation throttling without switching Chrome's visible tab.
- **Send visible text.** Offscreen article bodies and footers do not fill the model context.
- **Reuse an interrupted text request.** A generated value survives a stale-page retry only if the entire text-helper input is unchanged.

Every executed target is resolved from an observed node. The executor rechecks page freshness and click occlusion. Model output never becomes selectors, coordinates, shell commands, or executable JavaScript. Text-helper output must parse as a small JSON object before typing.

## Small enough to read

| File | Job |
| --- | --- |
| [agent.py](jev_ultrafast/agent.py) | The complete loop and text-helper handoff |
| [snapshot.js](jev_ultrafast/snapshot.js) | Atomic DOM snapshot, indexed controls, freshness guards |
| [browser.py](jev_ultrafast/browser.py) | Browser connection, current geometry, execution |
| [model.py](jev_ultrafast/model.py) | Dynamic operation/target heads and text generation |
| [questions.py](jev_ultrafast/questions.py) | Model instructions |
| [demo.py](jev_ultrafast/demo.py) | Local inspector |

## Evidence and limits

This fork’s [Clef verification record](docs/clef-verification.md) covers the live REST boundary, independently verified navigation, offline tests, and remaining text-helper setup. Run `uv run --env-file .env python scripts/smoke_navigation.py` to repeat the navigation check with a connected browser. This calls Cloudflare; it is not part of the offline suite.

All timings in this section and the linked historical performance documents are **upstream TypeSafe/Jev results**, not Clef-Flash benchmarks. The upstream video is a **7,073 ms** Google Flights run. Timing starts after initial page observation and includes model calls, generated text, browser work, stale decisions, and loading waits. A fresh independent check verifies the one-way setting, Zürich, London, September 20, 2026, and visible flight options. The video plays at 1×, with no opening hold and a 0.5-second final hold.

In six alternating runs with identical models and settings, both versions passed **3/3**. Median task time went from **9.450 s → 7.092 s**, a **25% reduction**; median browser protocol calls went from **1,092 → 101**. This is three repeats of one task on one browser profile, not a general reliability benchmark.

The same policy opened the requested Wikipedia article in **2.798 s** and passed a local hotel search/filter task in **1.896 s**. Runs, failures, source hashes, and measurement boundaries are in [performance.md](docs/performance.md).

A `DONE` choice still requires independent outcome verification. The DOM reader handles common HTML and ARIA controls, not the full accessible-name specification. Shadow roots, frames, canvas, uploads, pop-up tabs, nested scrolling, and arbitrary keyboard widgets remain outside this MVP. Owned tabs share the existing Chrome profile.

## Development

```bash
uv run ruff check .
uv run pytest
node --check jev_ultrafast/static/app.js
node --check jev_ultrafast/snapshot.js
uv build
```

Tests are offline. `uv run python scripts/check_guards.py` checks real controls in a local browser without model calls. Live examples and recording scripts make paid API calls. `scripts/record_flights.py <new-folder>` captures original browser timestamps; `scripts/render_demo.py <recording-folder>` renders that verified run at 1× and crops out the Google account strip. Credentials and raw traces stay ignored.

---

[Browser Use](https://github.com/browser-use/browser-use) · [Browser Harness](https://github.com/browser-use/browser-harness) · [TypeSafe speculative fan-out](https://docs.typesafe.ai/patterns/fan-out)

## License

The application remains MIT; the original Browser Use copyright and [LICENSE](LICENSE) are retained. Clef model files have a separate Apache-2.0 license and are not bundled here.
