"""Explicit live Clef smoke: navigate a local fixture and independently verify it.

Calls the paid Cloudflare API. Never collected by pytest. No text-helper key needed.
"""

import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jev_ultrafast import Agent
from jev_ultrafast.demo import ROOT, load_environment


def main():
    load_environment()
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(ROOT / "static"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/fixture.html?scenario=research"
    output = Path("artifacts/clef/navigation.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Agent(url, 'Open the article "A browser is a choice, not a conversation".') as agent:
            for state in agent.run():
                print(state["elapsed_ms"], state["status"], flush=True)
            # Read fresh browser state independently of the model's DONE response.
            actual = agent.browser.evaluate("({url:location.href, title:document.title, text:document.body.innerText})")
            checks = {
                "url": actual["url"] == url + "#choices",
                "title": actual["title"] == "A browser is a choice, not a conversation · Forma",
                "content": "Freshness is part of correctness." in actual["text"],
                "executed_click": any(h["kind"] == "click" for h in state["history"]),
            }
            result = {"verified": all(checks.values()), "checks": checks, "actual": actual,
                      "state": agent.snapshot()}
            output.write_text(json.dumps(result, indent=2))
            assert state["status"] == "done" and result["verified"], checks
            print(json.dumps({"verified": True, "checks": checks,
                              "decisions": len(state["decisions"]), "actions": len(state["history"]),
                              "text_calls": len(state["text_calls"]), "elapsed_ms": state["elapsed_ms"]}))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
