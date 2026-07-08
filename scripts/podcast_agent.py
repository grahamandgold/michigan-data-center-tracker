#!/usr/bin/env python3
"""Daily Michigan Data Wire podcast — two hosts talk through the past day's
verified headlines with context.

Pipeline (runs in GitHub Actions daily):
  1. Grok writes a two-host dialogue from live-data.json + upcoming meetings.
     Hosts: "Ada" (anchor, reads the news) and "Mack" (analyst, adds context).
     Script cites outlets by name and sticks to the verified deks — the agent
     may add CONTEXT (what it means, who decides next) but never new facts.
  2. Each line is synthesized with ElevenLabs (two distinct voices), falling
     back to OpenAI TTS if ELEVENLABS_API_KEY is absent.
  3. ffmpeg stitches segments into pod/latest.mp3 (+ dated archive copy) and
     pod/latest.json metadata that the homepage player reads at runtime.

Secrets: XAI_API_KEY (script) + ELEVENLABS_API_KEY or OPENAI_API_KEY (voices).
If no TTS key is configured the job still writes pod/latest-script.json so a
human (or another tool) can voice it.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POD = ROOT / "pod"
XAI_KEY = os.environ.get("XAI_API_KEY", "")
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4")
ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

# Two distinct default voices per provider (override with repo variables)
ELEVEN_VOICES = {"Ada": os.environ.get("VOICE_ADA", "EXAVITQu4vr4xnSDxMaL"),
                 "Mack": os.environ.get("VOICE_MACK", "TxGEqnHWrfWFTfGW9XjX")}
OPENAI_VOICES = {"Ada": os.environ.get("VOICE_ADA", "nova"),
                 "Mack": os.environ.get("VOICE_MACK", "onyx")}


def post_json(url: str, body: dict, headers: dict, timeout: int = 420) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def write_script() -> dict | None:
    live = json.loads((ROOT / "live-data.json").read_text(encoding="utf-8"))
    stories = live.get("stories", [])[:10]
    meetings = live.get("meetings", [])[:5]
    digest = "\n".join(f"- [{s.get('cat')}] {s.get('title')} — {s.get('dek')} (Source: {s.get('source')})"
                       for s in stories)
    mdigest = "\n".join(f"- {m.get('iso')} {m.get('body')}: {m.get('topic')}" for m in meetings)
    prompt = f"""Write today's episode of "Michigan Data Wire" — a tight 6-8 minute two-host
news audio show for {datetime.now(timezone.utc).strftime('%A, %B %d, %Y')}.

HOSTS: Ada (anchor — crisp, reads the headline facts) and Mack (analyst — adds
context: why it matters, who decides next, what to watch). Conversational but
newsroom-professional. No banter padding, no opinions on whether data centers
are good or bad — evenhanded public-interest journalism.

VERIFIED HEADLINES (your ONLY source of facts — cite outlets by name):
{digest}

UPCOMING MEETINGS:
{mdigest}

RULES: Never invent facts, numbers, quotes, or events beyond the digest. Context
must be framing ("that hearing is five days out", "this joins two other Kalamazoo-area
pauses") derivable from the digest itself. Open with the single biggest story.
Close with the meetings listeners can attend and "full sources at the Michigan
Data Center Tracker."

Respond ONLY with JSON:
{{"title": "<episode title>", "teaser": "<one-line teaser for the player, under 90 chars>",
 "lines": [{{"host": "Ada|Mack", "text": "<one spoken line, 1-3 sentences>"}}]}}
Aim for 40-60 lines total."""
    try:
        out = post_json("https://api.x.ai/v1/chat/completions",
                        {"model": XAI_MODEL, "messages": [{"role": "user", "content": prompt}],
                         "search_parameters": {"mode": "off"}, "temperature": 0.4},
                        {"Authorization": f"Bearer {XAI_KEY}"})
        text = out["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", text, re.S)
        script = json.loads(m.group(0))
        lines = [l for l in script.get("lines", [])
                 if l.get("host") in ("Ada", "Mack") and isinstance(l.get("text"), str) and l["text"].strip()]
        if len(lines) < 10:
            print("::warning::script too short")
            return None
        script["lines"] = lines
        return script
    except Exception as e:  # noqa: BLE001
        print(f"::warning::script generation failed: {e}")
        return None


def tts_eleven(text: str, voice: str, path: Path) -> bool:
    try:
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
            data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode(),
            headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            path.write_bytes(r.read())
        return True
    except Exception as e:  # noqa: BLE001
        print(f"::warning::elevenlabs tts failed: {e}")
        return False


def tts_openai(text: str, voice: str, path: Path) -> bool:
    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/speech",
            data=json.dumps({"model": "gpt-4o-mini-tts", "voice": voice, "input": text,
                             "response_format": "mp3"}).encode(),
            headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            path.write_bytes(r.read())
        return True
    except Exception as e:  # noqa: BLE001
        print(f"::warning::openai tts failed: {e}")
        return False


def main() -> int:
    if not XAI_KEY:
        print("::error::XAI_API_KEY not set")
        return 1
    POD.mkdir(exist_ok=True)
    script = write_script()
    if not script:
        print("Keeping yesterday's episode.")
        return 0
    (POD / "latest-script.json").write_text(json.dumps(script, indent=1, ensure_ascii=False), encoding="utf-8")

    if not (ELEVEN_KEY or OPENAI_KEY):
        print("::warning::no TTS key configured — script written, audio skipped")
        return 0

    seg_dir = POD / "_segments"
    seg_dir.mkdir(exist_ok=True)
    segs = []
    for i, line in enumerate(script["lines"]):
        seg = seg_dir / f"{i:03d}.mp3"
        ok = (tts_eleven(line["text"], ELEVEN_VOICES[line["host"]], seg) if ELEVEN_KEY
              else tts_openai(line["text"], OPENAI_VOICES[line["host"]], seg))
        if ok:
            segs.append(seg)
    if len(segs) < len(script["lines"]) * 0.8:
        print("::warning::too many TTS failures — keeping yesterday's episode")
        return 0

    concat = seg_dir / "list.txt"
    concat.write_text("\n".join(f"file '{s.name}'" for s in segs), encoding="utf-8")
    out = POD / "latest.mp3"
    try:
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
                        "-c:a", "libmp3lame", "-b:a", "128k", str(out)],
                       check=True, cwd=seg_dir, capture_output=True)
        probe = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(out)], capture_output=True, text=True, check=True)
        minutes = max(1, round(float(probe.stdout.strip()) / 60))
    except Exception as e:  # noqa: BLE001
        print(f"::error::ffmpeg stitch failed: {e}")
        return 1

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (POD / f"{today}.mp3").write_bytes(out.read_bytes())
    (POD / "latest.json").write_text(json.dumps({
        "date": today, "title": script.get("title", "Michigan Data Wire"),
        "teaser": script.get("teaser", ""), "minutes": minutes,
        "audio": "pod/latest.mp3", "hosts": ["Ada", "Mack"],
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    # keep the repo lean: archive only the last 7 dated episodes
    dated = sorted(POD.glob("2*.mp3"))
    for old in dated[:-7]:
        old.unlink()
    for f in seg_dir.iterdir():
        f.unlink()
    seg_dir.rmdir()
    print(f"Episode built: {minutes} min, {len(segs)} segments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
