"""Offline proofs of the Cloudflare REST boundary; no paid model calls."""

import json
from unittest.mock import Mock

import httpx
import pytest

from jev_ultrafast import agent as loop
from jev_ultrafast import model

PAGE = {"url": "https://example.test", "title": "Reading room", "text": "Articles", "actions": [
    {"id": "e1", "kind": "click", "label": "Choices", "node": 1},
    {"id": "e2", "kind": "click", "label": "Other", "node": 2},
]}


def choice(ids, selected):
    return {"type": "choice", "choice": selected, "confidence": 1.0,
            "probabilities": {i: float(i == selected) for i in ids}}


def envelope():
    return {"success": True, "errors": [], "messages": [], "result": {
        "model": "clef", "usage": {"input_tokens": 843, "output_tokens": 0},
        "answers": {"operation": choice(["CLICK", "DONE", "BLOCKED"], "CLICK"),
                    "click_target": choice(["1", "2"], "1")},
    }}


@pytest.fixture
def credentials(monkeypatch):
    monkeypatch.delenv("CLEF_MODEL", raising=False)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")


def test_rest_request_and_envelope_reach_existing_validator(monkeypatch, credentials):
    def handle(request):
        assert str(request.url) == (
            "https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/ai/run/@cf/cloudflare/clef"
        )
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.headers["Content-Type"] == "application/json"
        body = json.loads(request.content)
        assert body["model"] == "clef"
        assert body["state"]["page"]["url"] == PAGE["url"]
        assert body["state"]["goal"] == "Open Choices"
        assert set(body["questions"]) == {"operation", "click_target"}
        return httpx.Response(200, json=envelope())

    monkeypatch.setattr(model, "CLIENT", httpx.Client(transport=httpx.MockTransport(handle)))
    validate = Mock(wraps=model.validate_choice)
    monkeypatch.setattr(model, "validate_choice", validate)
    decision = model.choose(PAGE, "Open Choices", [])
    assert decision["choice"] == "e1"
    assert decision["usage"]["input_tokens"] == 843
    assert validate.call_count == 2


@pytest.mark.parametrize("response", [
    None, [], {}, {"success": False, "result": {}}, {"success": 1, "result": {}},
    {"success": True, "errors": [{"message": "provider failed"}], "result": {}},
    {"success": True, "result": None},
    {"success": True, "result": {"model": "clef-flash", "answers": []}},
    {"success": True, "result": {"answers": {}}},
    {"success": True, "result": {"model": "clef-flash", "answers": {}, "usage": []}},
    {"success": True, "result": {"model": "clef-flash", "answers": {}}},
    {"success": True, "result": {"model": "clef-flash", "answers": {"operation": {"probabilities": []}}}},
])
def test_bad_rest_response_cannot_execute(monkeypatch, credentials, response):
    monkeypatch.setattr(model, "post_json", Mock(return_value=response))
    a = loop.Agent.__new__(loop.Agent)
    a.screenshots = False
    a.state = {"browser": Mock(fresh=Mock(return_value=True)), "page": PAGE,
               "goal": "Open Choices", "history": [], "decisions": [],
               "status": "ready", "started_at": None, "decision": None}
    with pytest.raises(ValueError, match="no action executed"):
        a.command("tick")
    a.state["browser"].act.assert_not_called()
    assert a.state["decision"] is None


@pytest.mark.parametrize("missing", ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"])
def test_missing_credentials_never_call_provider(monkeypatch, credentials, missing):
    monkeypatch.delenv(missing)
    post = Mock()
    monkeypatch.setattr(model, "post_json", post)
    with pytest.raises(ValueError, match="CLOUDFLARE"):
        model.choose(PAGE, "Open Choices", [])
    post.assert_not_called()


@pytest.mark.parametrize("status,content", [(401, b'Unauthorized'), (200, b'not JSON')])
def test_http_and_non_json_fail_closed(monkeypatch, credentials, status, content):
    monkeypatch.setattr(model, "CLIENT", httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, content=content))))
    with pytest.raises((RuntimeError, ValueError), match="no action executed"):
        model.choose(PAGE, "Open Choices", [])


def test_singleton_target_is_observed_and_validated(monkeypatch, credentials):
    def post(url, key, body):
        assert set(body["questions"]) == {"operation"}
        result = envelope()
        del result["result"]["answers"]["click_target"]
        return result
    monkeypatch.setattr(model, "post_json", post)
    decision = model.choose({**PAGE, "actions": PAGE["actions"][:1]}, "Open Choices", [])
    assert decision["choice"] == "e1"
    assert decision["target_probabilities"] == {"1": 1.0}
    assert "click_target" not in decision["raw_answers"]


def test_text_provider_remains_configurable_and_unwrapped(monkeypatch):
    for name, value in {"TEXT_MODEL_API_KEY": "text-key", "TEXT_MODEL": "custom-model",
                        "TEXT_MODEL_BASE_URL": "https://text.example/v1", "TEXT_MODEL_REASONING": "none"}.items():
        monkeypatch.setenv(name, value)

    def handle(request):
        assert str(request.url) == "https://text.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer text-key"
        body = json.loads(request.content)
        assert body["model"] == "custom-model"
        assert body["response_format"] == {"type": "json_object"}
        assert body["reasoning"] == {"enabled": False}
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"text":"Lisbon"}'}}]})

    monkeypatch.setattr(model, "CLIENT", httpx.Client(transport=httpx.MockTransport(handle)))
    assert model.field_text({"goal": "Search Lisbon"})[0] == "Lisbon"


def test_cloudflare_text_defaults_use_account_token(monkeypatch, credentials):
    for key in ("TEXT_MODEL", "TEXT_MODEL_BASE_URL", "TEXT_MODEL_API_KEY", "TEXT_MODEL_REASONING"):
        monkeypatch.setenv(key, "")

    def handle(request):
        expected = "https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/ai/v1/chat/completions"
        assert str(request.url) == expected
        assert request.headers["Authorization"] == "Bearer test-token"
        body = json.loads(request.content)
        assert body["model"] == "@cf/openai/gpt-oss-20b"
        assert body["reasoning_effort"] == "low"
        assert "reasoning" not in body
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"text":"London"}'}}]})

    monkeypatch.setattr(model, "CLIENT", httpx.Client(transport=httpx.MockTransport(handle)))
    assert model.field_text({"goal": "Zurich to London", "field": {"label": "Where to?"}})[0] == "London"


def test_cloudflare_token_is_never_forwarded_to_custom_text_endpoint(monkeypatch, credentials):
    monkeypatch.setenv("TEXT_MODEL_BASE_URL", "https://other.example/v1")
    monkeypatch.delenv("TEXT_MODEL_API_KEY", raising=False)
    post = Mock()
    monkeypatch.setattr(model, "post_json", post)
    with pytest.raises(ValueError, match="TEXT_MODEL_API_KEY"):
        model.field_text({})
    post.assert_not_called()


@pytest.mark.parametrize("name", ["clef", "clef-flash"])
def test_clef_model_endpoint_matches_request(monkeypatch, credentials, name):
    monkeypatch.setenv("CLEF_MODEL", name)

    def post(url, key, body):
        assert url.endswith("/ai/run/@cf/cloudflare/" + name)
        assert body["model"] == name
        result = envelope()
        result["result"]["model"] = name
        return result

    monkeypatch.setattr(model, "post_json", post)
    assert model.choose(PAGE, "Open Choices", [])["model"] == name


def test_unknown_clef_model_cannot_call_provider(monkeypatch, credentials):
    monkeypatch.setenv("CLEF_MODEL", "../../other")
    post = Mock()
    monkeypatch.setattr(model, "post_json", post)
    with pytest.raises(ValueError, match="CLEF_MODEL"):
        model.choose(PAGE, "Open Choices", [])
    post.assert_not_called()
