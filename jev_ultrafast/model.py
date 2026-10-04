"""Cloudflare Clef models make choices; a configurable text model writes field values."""

import json
import math
import os
import time

import httpx

from .questions import NEXT_ACTION, TARGET, TEXT_VALUE

CLIENT = httpx.Client(http2=True, timeout=25)


def post_json(url, key, body):
    for attempt in range(3):
        try:
            response = CLIENT.post(url, json=body, headers={"Authorization": f"Bearer {key}"})
        except httpx.HTTPError:
            raise RuntimeError("Model connection failed; no action executed.") from None
        if response.status_code in {429, 529, 503} and attempt < 2:
            time.sleep(0.5 * 2**attempt)
            continue
        if response.is_error:
            raise RuntimeError(f"Model provider returned HTTP {response.status_code}; no action executed.")
        return response.json()
    raise RuntimeError("Model unavailable")


def clef_decision(body):
    """Unwrap Workers AI REST transport without changing the text helper's transport."""
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not account or not token:
        raise ValueError("Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN; no action executed.")
    if len(account) != 32 or any(c not in "0123456789abcdef" for c in account.lower()):
        raise ValueError("Invalid CLOUDFLARE_ACCOUNT_ID; no action executed.")
    selected_model = body["model"]
    if selected_model not in {"clef-flash", "clef"}:
        raise ValueError("CLEF_MODEL must be clef-flash or clef; no action executed.")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/cloudflare/{selected_model}"
    try:
        envelope = post_json(url, token, body)
    except ValueError:
        raise ValueError("Invalid Cloudflare JSON response; no action executed.") from None
    if not isinstance(envelope, dict) or envelope.get("success") is not True or envelope.get("errors"):
        raise ValueError("Unsuccessful Cloudflare response; no action executed.")
    result = envelope.get("result")
    if (
        not isinstance(result, dict)
        or not isinstance(result.get("model"), str)
        or not result["model"].strip()
        or not isinstance(result.get("answers"), dict)
        or ("usage" in result and not isinstance(result["usage"], dict))
    ):
        raise ValueError("Invalid Clef response; no action executed.")
    return result


def validate_choice(answer, ids):
    try:
        probabilities = answer["probabilities"]
        numbers = [*probabilities.values(), answer["confidence"]]
        valid = (
            answer["choice"] in ids
            and set(probabilities) == set(ids)
            and all(type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1 for n in numbers)
            and abs(sum(probabilities.values()) - 1) < 0.02
            and probabilities[answer["choice"]] >= max(probabilities.values()) - 1e-6
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("Invalid Clef response; no action executed.")
    return answer


def action_space(actions):
    """One index per observed element; each operation has its own valid target choices."""
    elements, indices, targets, controls = [], {}, {}, {}
    operations = {"click": "CLICK", "fill": "TYPE_TEXT", "select": "SELECT"}
    for action in actions:
        kind = action["kind"]
        if kind not in operations:
            controls[action["id"].upper()] = action
            continue
        node = action["node"]
        if node not in indices:
            index = str(len(elements) + 1)
            indices[node] = index
            element = {k: action[k] for k in ("role", "value", "checked", "selected", "expanded") if k in action}
            element.update(index=index, label=action["label"].split(" → ")[0], operations=[])
            if kind == "select":
                element["value"] = action.get("current_value", "")
                element["options"] = []
            elements.append(element)
        index = indices[node]
        operation = operations[kind]
        group = targets.setdefault(operation, {})
        element = elements[int(index) - 1]
        if operation not in element["operations"]:
            element["operations"].append(operation)
        target = index
        if kind == "select":
            target = f"{index}:{len(element['options']) + 1}"
            element["options"].append({"index": target, "label": action["label"], "value": action["value"]})
        group[target] = action
    return elements, targets, controls


def choose(state, goal, history):
    elements, targets, controls = action_space(state["actions"])
    labels = {
        "CLICK": "Click an element, button, menu option, autocomplete suggestion, or calendar day.",
        "TYPE_TEXT": "Enter or replace text in an editable field. A small LLM will supply the value from the goal.",
        "SELECT": "Select an observed dropdown value.",
    }
    operations = {key: labels[key] for key in targets}
    operations.update({key: value["label"] for key, value in controls.items()})
    operations.update(DONE="Every requirement is visibly satisfied.", BLOCKED="No supported operation can progress.")
    questions = {
        "operation": {"type": "choice", "criteria": operations, "instructions": {"goal": goal, "rules": NEXT_ACTION}}
    }
    for operation, candidates in targets.items():
        # Clef rejects choice questions with fewer than two options (HTTP 422).
        # A singleton target is already fixed by the selected operation.
        if len(candidates) == 1:
            continue
        questions[operation.lower() + "_target"] = {
            "type": "choice",
            "criteria": {
                index: {
                    "element": f"[{index}] {a['label']}",
                    "current_value": a.get("current_value", a.get("value", "")),
                    **{k: a[k] for k in ("role", "checked", "selected", "expanded") if k in a},
                }
                for index, a in candidates.items()
            },
            "instructions": {"goal": goal, "operation": operation, "rules": [NEXT_ACTION, TARGET]},
        }
    body = {
        "model": os.environ.get("CLEF_MODEL") or "clef-flash",
        "state": {
            "goal": goal,
            "page": {k: state[k] for k in ("url", "title", "text")},
            "elements": elements,
            "recent_actions": [
                {k: h.get(k) for k in ("action", "kind", "text", "page_changed")} for h in history[-10:]
            ],
        },
        "questions": questions,
    }
    started = time.perf_counter()
    result = clef_decision(body)
    operation_answer = validate_choice(result["answers"].get("operation", {}), operations)
    operation = operation_answer["choice"]
    target = None
    target_answer = None
    probabilities = {}
    if operation in targets:
        # Unused target heads cannot cause an action. Validate the head selected by the operation.
        candidates = targets[operation]
        if len(candidates) == 1:
            only = next(iter(candidates))
            answer = {"choice": only, "probabilities": {only: 1.0}, "confidence": 1.0}
        else:
            answer = result["answers"].get(operation.lower() + "_target", {})
        target_answer = validate_choice(answer, candidates)
        target = target_answer["choice"]
        choice = targets[operation][target]["id"]
        probabilities = {a["id"]: target_answer["probabilities"][index] for index, a in targets[operation].items()}
    else:
        choice = controls[operation]["id"] if operation in controls else operation
        probabilities[choice] = operation_answer["probabilities"][operation]
    return {
        "choice": choice,
        "operation": operation,
        "target": target,
        "confidence": operation_answer["confidence"],
        "probabilities": probabilities,
        "operation_probabilities": operation_answer["probabilities"],
        "target_probabilities": target_answer["probabilities"] if target_answer else {},
        "target_confidence": target_answer["confidence"] if target_answer else None,
        "raw_answers": result["answers"],
        "model": result["model"],
        "usage": result.get("usage", {}),
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "request": body,
    }


def field_context(goal, action, page, history):
    return {
        "goal": goal,
        "field": {k: action.get(k) for k in ("label", "role", "value")},
        "page": {"title": page["title"], "text": page["text"][:6000]},
        "recent_actions": [{k: h.get(k) for k in ("action", "text")} for h in history[-6:]],
    }


DEFAULT_TEXT_MODEL = "@cf/openai/gpt-oss-20b"


def text_configuration():
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    cloudflare_base = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1"
    base = (os.environ.get("TEXT_MODEL_BASE_URL") or cloudflare_base).rstrip("/")
    cloudflare = base == cloudflare_base
    key = os.environ.get("TEXT_MODEL_API_KEY") or (os.environ.get("CLOUDFLARE_API_TOKEN") if cloudflare else None)
    if not key or (cloudflare and not account):
        raise ValueError("TYPE_TEXT needs Cloudflare credentials or TEXT_MODEL_API_KEY for an explicit text endpoint.")
    model = os.environ.get("TEXT_MODEL") or DEFAULT_TEXT_MODEL
    effort = os.environ.get("TEXT_MODEL_REASONING") or ("low" if cloudflare else "omit")
    if effort == "omit":
        reasoning = {}
    elif effort == "none":
        reasoning = {"reasoning": {"enabled": False}}
    elif cloudflare:
        reasoning = {"reasoning_effort": effort}
    else:
        reasoning = {"reasoning": {"effort": effort}}
    return base, key, model, reasoning


def field_text(context):
    base, key, model, reasoning = text_configuration()
    started = time.perf_counter()
    result = post_json(
        base + "/chat/completions",
        key,
        {
            "model": model,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
            **reasoning,
            "messages": [
                {"role": "system", "content": TEXT_VALUE},
                {
                    "role": "user",
                    "content": json.dumps(context),
                },
            ],
        },
    )
    try:
        output = json.loads(result["choices"][0]["message"]["content"])
        value = output["text"]
        if set(output) != {"text"} or not isinstance(value, str) or not value.strip() or len(value) > 2000:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise ValueError("Text helper returned no valid field value; nothing typed.") from None
    return value, {
        "model": model,
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "usage": result.get("usage", {}),
    }
