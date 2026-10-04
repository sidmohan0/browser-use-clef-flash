# Attribution

## Application and upstream work

Browser Use Clef-Flash is an independent fork of [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast), originally developed by Browser Use and licensed under MIT. The original copyright and license text are preserved in [LICENSE](LICENSE). Sid Mohan maintains this fork and its Cloudflare integration, verification, and comparison documentation.

This project is not maintained or endorsed by Browser Use, Cloudflare, or TypeSafe. Product and organization names identify the relevant projects and services.

## Demonstrations and measurements

The original `docs/demo.gif`, `docs/demo.mp4`, and historical performance documents are retained from upstream and describe TypeSafe/Jev runs. The local inspector’s upstream video link refers to that original demonstration.

The `docs/cloudflare-flights.*` recording and verification files and `docs/provider-comparison.json` describe this fork’s experiments. Their dates, measurement boundaries, and limitations are documented in the README. Upstream results must not be presented as Cloudflare measurements.

## External models and dependencies

[Clef](https://huggingface.co/Cloudflare/clef) and [Clef-Flash](https://huggingface.co/Cloudflare/clef-flash) publish their model files under Apache-2.0. This repository calls hosted inference endpoints and does not include model weights. Other configured models and hosted APIs remain subject to their respective licenses and service terms; the application’s MIT license does not replace them.

Python dependencies are declared in `pyproject.toml` and pinned in `uv.lock`; each retains its own license. Browser Harness is an upstream dependency, not part of this fork’s original work.
