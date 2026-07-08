#!/usr/bin/env python3
"""Shared xAI helper — Responses API with server-side search tools.

xAI deprecated Live Search (`search_parameters`) in favor of the Agent Tools
API on `/v1/responses`. This client:
  * converts our old chat-completions-style bodies to Responses API calls,
  * maps `search_parameters.mode on/auto` -> tools [web_search, x_search],
  * auto-discovers the newest grok model if the configured one is retired,
  * returns a chat-completions-shaped dict so callers stay unchanged.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

API = "https://api.x.ai/v1"
DEFAULT_MODEL = "grok-4-1-fast-reasoning"


def _get(url: str, key: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def discover_model(key: str) -> str | None:
    """Newest available grok text model (skips image/video/embedding models)."""
    try:
        models = _get(API + "/models", key).get("data", [])
    except Exception as e:  # noqa: BLE001
        print(f"::warning::model discovery failed: {e}")
        return None
    cands = [m for m in models
             if str(m.get("id", "")).startswith("grok")
             and not any(x in str(m.get("id", "")) for x in ("image", "video", "embed", "vision", "imagine"))]
    if not cands:
        return None
    cands.sort(key=lambda m: (m.get("created", 0), str(m.get("id", ""))), reverse=True)
    picked = cands[0]["id"]
    print(f"model discovery: using '{picked}'")
    return picked


def _extract_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str) and data["output_text"]:
        return data["output_text"]
    text = ""
    for item in data.get("output", []) or []:
        if item.get("type") == "message":
            for c in item.get("content", []) or []:
                if c.get("type") in ("output_text", "text"):
                    text += c.get("text", "")
    return text


def chat(key: str, body: dict, timeout: int = 420) -> dict | None:
    """Accepts an old chat-completions-style body; calls /v1/responses.

    Returns {"choices": [{"message": {"content": <text>}}]} or None.
    """
    body = dict(body)
    model = os.environ.get("XAI_MODEL") or body.get("model") or DEFAULT_MODEL
    if model in ("grok-4", ""):  # retired alias from older configs
        model = DEFAULT_MODEL
    sp = body.pop("search_parameters", None) or {}
    want_search = str(sp.get("mode", "off")) in ("on", "auto", "True", "true")

    rbody: dict = {"model": model, "input": body.get("messages", [])}
    if body.get("temperature") is not None:
        rbody["temperature"] = body["temperature"]
    if want_search:
        rbody["tools"] = [{"type": "web_search"}, {"type": "x_search"}]

    for attempt in (1, 2):
        req = urllib.request.Request(
            API + "/responses", data=json.dumps(rbody).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
            text = _extract_text(data)
            if not text:
                print("::warning::empty output from responses API")
                return None
            return {"choices": [{"message": {"content": text}}]}
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode()[:200]
            except Exception:  # noqa: BLE001
                pass
            print(f"::warning::xAI call failed ({e.code}) with model '{rbody['model']}': {detail}")
            if attempt == 1 and e.code in (400, 404, 410, 422):
                found = discover_model(key)
                if found and found != rbody["model"]:
                    rbody["model"] = found
                    continue
            return None
        except Exception as e:  # noqa: BLE001
            print(f"::warning::xAI call failed: {e}")
            return None
    return None
