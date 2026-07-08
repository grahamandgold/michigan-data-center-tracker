#!/usr/bin/env python3
"""multi_ai_client — one client, three model families, routed by capability.

The newsroom's division of labor:

  capability    default provider   why
  ----------    ----------------   -----------------------------------------
  hunting       xai (Grok)         real-time web_search + x_search tools
  judgment      anthropic (Claude) editorial judgment, standards, writing
  extraction    openai (GPT-4o)    structured JSON out of messy documents
  vision        openai (GPT-4o)    reading rendered pages / scanned PDFs

Every capability degrades gracefully: if the preferred provider's API key is
missing or the call fails, we fall through the chain and ultimately land on
xAI (whose key is already wired into every workflow). Scripts never break
because a new key isn't set yet.

Override routing without code changes:
  ROUTE_JUDGMENT=openai  ROUTE_EXTRACTION=anthropic  etc.

Usage:
  import multi_ai_client as ai
  text = ai.chat("judgment", [{"role": "user", "content": prompt}], temperature=0)
  text = ai.chat("hunting", msgs, search=True)          # Grok live search
  text = ai.vision("vision", prompt, [png_bytes, ...])  # images -> text

Stdlib only. Requires whichever of XAI_API_KEY / ANTHROPIC_API_KEY /
OPENAI_API_KEY you have; XAI_API_KEY alone is enough to run everything.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
OPENAI_API = "https://api.openai.com/v1/chat/completions"

DEFAULT_MODELS = {
    "anthropic": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
    "openai": os.environ.get("OPENAI_MODEL", "gpt-4o"),
}

# preferred provider first, then fallbacks (only providers with keys are tried)
ROUTES = {
    "hunting": ["xai", "openai", "anthropic"],
    "judgment": ["anthropic", "openai", "xai"],
    "extraction": ["openai", "anthropic", "xai"],
    "vision": ["openai", "anthropic"],
}


def _key(provider: str) -> str:
    return os.environ.get({"xai": "XAI_API_KEY",
                           "anthropic": "ANTHROPIC_API_KEY",
                           "openai": "OPENAI_API_KEY"}[provider], "")


def _providers_for(capability: str) -> list[str]:
    override = os.environ.get(f"ROUTE_{capability.upper()}", "")
    chain = ([override] if override else []) + ROUTES.get(capability, ["xai"])
    seen, out = set(), []
    for p in chain:
        if p in ("xai", "anthropic", "openai") and p not in seen and _key(p):
            seen.add(p)
            out.append(p)
    return out


def _post(url: str, headers: dict, body: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------- providers
def _call_xai(messages: list, temperature: float, search: bool, timeout: int) -> str | None:
    import xai_client
    body = {"messages": messages, "temperature": temperature,
            "search_parameters": {"mode": "on" if search else "off"}}
    out = xai_client.chat(_key("xai"), body, timeout=timeout)
    try:
        return out["choices"][0]["message"]["content"] if out else None
    except (KeyError, IndexError, TypeError):
        return None


def _call_anthropic(messages: list, temperature: float, timeout: int,
                    images: list[bytes] | None = None) -> str | None:
    system = "\n".join(m["content"] for m in messages if m.get("role") == "system") or None
    turns = []
    for m in messages:
        if m.get("role") == "system":
            continue
        turns.append({"role": m["role"], "content": m["content"]})
    if images and turns:
        content = [{"type": "image",
                    "source": {"type": "base64", "media_type": "image/png",
                               "data": base64.b64encode(img).decode()}} for img in images]
        content.append({"type": "text", "text": turns[-1]["content"]})
        turns[-1] = {"role": turns[-1]["role"], "content": content}
    body = {"model": DEFAULT_MODELS["anthropic"], "max_tokens": 4096,
            "temperature": temperature, "messages": turns}
    if system:
        body["system"] = system
    data = _post(ANTHROPIC_API,
                 {"x-api-key": _key("anthropic"), "anthropic-version": "2023-06-01"},
                 body, timeout)
    try:
        return "".join(b.get("text", "") for b in data.get("content", []))
    except Exception:  # noqa: BLE001
        return None


def _call_openai(messages: list, temperature: float, timeout: int,
                 images: list[bytes] | None = None) -> str | None:
    msgs = [dict(m) for m in messages]
    if images and msgs:
        content = [{"type": "text", "text": msgs[-1]["content"]}]
        content += [{"type": "image_url",
                     "image_url": {"url": "data:image/png;base64,"
                                          + base64.b64encode(img).decode()}} for img in images]
        msgs[-1] = {"role": msgs[-1]["role"], "content": content}
    body = {"model": DEFAULT_MODELS["openai"], "temperature": temperature, "messages": msgs}
    data = _post(OPENAI_API, {"Authorization": f"Bearer {_key('openai')}"}, body, timeout)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return None


# ---------------------------------------------------------------- public API
def chat(capability: str, messages: list, temperature: float = 0.2,
         search: bool = False, timeout: int = 300) -> str | None:
    """Route a chat to the right model family. Returns text or None."""
    for provider in _providers_for(capability):
        try:
            if provider == "xai":
                text = _call_xai(messages, temperature, search, timeout)
            elif provider == "anthropic":
                text = _call_anthropic(messages, temperature, timeout)
            else:
                text = _call_openai(messages, temperature, timeout)
            if text:
                return text
            print(f"::warning::{provider} returned empty for '{capability}', trying next")
        except urllib.error.HTTPError as e:
            print(f"::warning::{provider} HTTP {e.code} for '{capability}', trying next")
        except Exception as e:  # noqa: BLE001
            print(f"::warning::{provider} failed for '{capability}': {e}")
    return None


def vision(capability: str, prompt: str, images: list[bytes],
           temperature: float = 0.0, timeout: int = 300) -> str | None:
    """Send PNG image bytes + a prompt to a vision-capable model."""
    messages = [{"role": "user", "content": prompt}]
    for provider in _providers_for(capability):
        try:
            if provider == "openai":
                text = _call_openai(messages, temperature, timeout, images=images)
            elif provider == "anthropic":
                text = _call_anthropic(messages, temperature, timeout, images=images)
            else:
                continue  # xai vision not wired
            if text:
                return text
        except Exception as e:  # noqa: BLE001
            print(f"::warning::{provider} vision failed: {e}")
    return None


def extract_json(text: str) -> dict | list | None:
    """Pull the first JSON object/array out of a model reply."""
    import re
    if not text:
        return None
    m = re.search(r"\{.*\}|\[.*\]", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":
    for cap in ROUTES:
        print(f"{cap:11s} -> {_providers_for(cap) or ['(no keys set)']}")
