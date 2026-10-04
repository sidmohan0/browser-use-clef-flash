# Contributing

Please open issues and pull requests in [sidmohan0/browser-use-clef-flash](https://github.com/sidmohan0/browser-use-clef-flash). Include reproduction steps and the relevant model/configuration for bugs. Remove credentials and private browser content from logs before sharing.

## Local development

Use Python 3.12 or newer, uv, and Chrome. Run `uv sync`, copy `.env.example` to `.env`, and follow the README for live Cloudflare access. Keep credentials in the ignored `.env`.

Before submitting changes, run:

```bash
uv run ruff check .
uv run pytest
node --check jev_ultrafast/static/app.js
node --check jev_ultrafast/snapshot.js
uv build
```

Tests must remain offline. Live examples call paid APIs and require your own account. Preserve the generic action loop, target validation, and browser freshness guards; do not add site-specific action plans or retry browser mutations.

## Reporting results

Verify final page outcomes independently of the model’s DONE choice. Report model versions, task, dates, run count, failures, timing boundaries, and recording overhead. Retain original-speed footage and distinguish upstream measurements from this fork’s results.

Changes are contributed under the repository’s MIT license. Preserve upstream attribution.
