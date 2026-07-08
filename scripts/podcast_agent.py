#!/usr/bin/env python3
"""Daily Michigan Data Wire podcast — two hosts talk through the past day's
verified headlines with context.

Pipeline (runs in GitHub Actions daily):
  1. Grok writes a two-host dialogue from live-data.json + upcoming meetings.
     Hosts: "Graham" (anchor, reads the news) and "Emmy" (analyst, adds context).
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

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
POD = ROOT / "pod"
XAI_KEY = os.environ.get("XAI_API_KEY", "")
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4")
ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

# Two distinct default voices per provider (override with repo variables)
ELEVEN_VOICES = {"Graham": os.environ.get("VOICE_GRAHAM", "TxGEqnHWrfWFTfGW9XjX"),
                 "Emmy": os.environ.get("VOICE_EMMY", "EXAVITQu4vr4xnSDxMaL")}
OPENAI_VOICES = {"Graham": os.environ.get("VOICE_GRAHAM", "onyx"),
                 "Emmy": os.environ.get("VOICE_EMMY", "nova")}


def post_json(url: str, body: dict, headers: dict, timeout: int = 420) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def director_notes() -> str:
    """Standing notes from the News Director (agent-notes.json, set from the
    Intel Desk) + the compiled training memory. Injected as hard instructions."""
    out = ""
    try:
        notes = json.loads((ROOT / "agent-notes.json").read_text(encoding="utf-8")).get("notes", [])
        mine = [n for n in notes if n.get("agent") in ("All agents", "Streaming Producer")]
        if mine:
            out += ("\n\nSTANDING NOTES FROM THE NEWS DIRECTOR (obey these):\n"
                    + "\n".join(f"- {n['text']}" for n in mine))
    except Exception:  # noqa: BLE001
        pass
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        import lessons_util
        out += lessons_util.lessons_block(agent="podcast")
    except Exception:  # noqa: BLE001
        pass
    return out


def script_override() -> dict | None:
    """If the News Director edited today's script on the desk, voice HIS words."""
    try:
        ov = json.loads((ROOT / "pod" / "script-override.json").read_text(encoding="utf-8"))
        if ov.get("date") == datetime.now(timezone.utc).strftime("%Y-%m-%d") and len(ov.get("lines", [])) >= 5:
            print("Using the News Director's edited script (pod/script-override.json)")
            return ov
    except Exception:  # noqa: BLE001
        pass
    return None


def write_script() -> dict | None:
    override = script_override()
    if override:
        return override
    live = json.loads((ROOT / "live-data.json").read_text(encoding="utf-8"))
    stories = live.get("stories", [])[:10]
    meetings = live.get("meetings", [])[:5]
    def when(iso):
        try:
            t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            h = (datetime.now(timezone.utc) - t).total_seconds() / 3600
            if h <= 15:
                return "today"
            if h <= 36:
                return "yesterday"
            if h <= 24 * 7:
                return t.strftime("on %A")
            return "earlier " + ("this month" if h <= 24 * 31 else "this year")
        except Exception:  # noqa: BLE001
            return "recently"

    digest = "\n".join(
        f"- {'[LEAD] ' if s.get('lead') else ''}[{s.get('cat')}] (happened {when(s.get('iso'))}) {s.get('title')} — {s.get('dek')} (Source: {s.get('source')})"
        for s in stories)
    mdigest = "\n".join(f"- {m.get('iso')} {m.get('body')}: {m.get('topic')}" for m in meetings)
    prompt = f"""Write today's episode of "Michigan Data Wire" for {datetime.now(timezone.utc).strftime('%A, %B %d, %Y')}.
This is a two-host DAILY PODCAST — a real conversation, not headline reading.

HOSTS:
- Graham — the anchor. Warm, direct, sets up the story and keeps things moving.
- Emmy — the analyst. Curious, sharp, explains why it matters and what happens next.
They talk WITH each other: questions, reactions, follow-ups, natural spoken English
with contractions. Never read a list. Never say "headline" or "dek." No partisan takes.

LENGTH — HARD TARGET: the episode must run ABOUT 12 MINUTES when spoken.
That is roughly 1,700-1,900 words of dialogue — write 95-125 lines. Do not
come in under 90 lines. Fill the time with genuine depth (history, stakes,
what happens next), never with padding or repetition.

STRUCTURE (95-125 lines total):
1. COLD OPEN — Graham: "You're listening to the Michigan Data Wire — your daily
   podcast on Michigan's data center buildout. I'm Graham." Emmy: "And I'm Emmy."
   One line teasing today's big story.
2. THE BIG STORY (about 60%% of the show) — take the LEAD headline below and have a
   genuine conversation about the bigger issue behind it: the history of this fight,
   who the players are, what it means for electric bills, water, farmland, and towns,
   and what happens next. Emmy asks the questions a smart neighbor would ask; Graham
   grounds it in the facts. You may RESEARCH background for this segment (see rules).
3. QUICK HITS — the remaining stories in 1-2 conversational exchanges each,
   trading off who leads.
4. ON DECK — the upcoming meetings listeners can actually attend, conversationally.
5. SIGN-OFF — "Full sources and the live map at the Michigan Data Center Tracker.
   We're back tomorrow."

TODAY'S VERIFIED STORIES (the lead is marked; these are your news facts):
{digest}

UPCOMING MEETINGS:
{mdigest}

BALANCE — HARD RULE: if the digest covers a debate or multi-candidate event but
only includes ONE candidate's positions, you MUST research what the other major
candidates said at that same event and present their positions with equal weight
and attribution. If you cannot verify a rival's position, say on air that the
tracker is still gathering the other candidates' statements — never present one
side as the whole story.

TEMPORAL ACCURACY: each story above is labeled with WHEN it happened. Only say
"today" for stories labeled today. Say "yesterday", the weekday, or "this week"
exactly as labeled — never present older news as breaking. If researching
background, note when those events happened too.

RESEARCH RULES: For the big-story segment you may search for BACKGROUND context
(history, prior votes, how many townships have paused, what a gigawatt powers) —
but attribute anything specific ("MLive reported...", "according to the township")
and never invent quotes, numbers, or events. When unsure, speak generally.
The quick hits must stick strictly to the story summaries above.

Respond ONLY with JSON:
{{"title": "<episode title>", "teaser": "<one-line teaser for the player, under 90 chars>",
 "lines": [{{"host": "Graham|Emmy", "text": "<one spoken line, 1-3 sentences>"}}]}}{director_notes()}"""
    import xai_client
    out = xai_client.chat(XAI_KEY, {"model": XAI_MODEL, "messages": [{"role": "user", "content": prompt}],
                                    "search_parameters": {"mode": "on"}, "temperature": 0.6})
    if not out:
        return None
    try:
        text = out["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", text, re.S)
        script = json.loads(m.group(0))
        lines = [l for l in script.get("lines", [])
                 if l.get("host") in ("Graham", "Emmy") and isinstance(l.get("text"), str) and l["text"].strip()]
        if len(lines) < 60:
            print(f"::warning::script too short for a 12-minute show ({len(lines)} lines)")
            if len(lines) < 10:
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
            data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.42, "similarity_boost": 0.8, "style": 0.35}}).encode(),
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

    gap = seg_dir / "gap.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", "0.28", "-c:a", "libmp3lame", "-b:a", "128k", str(gap)],
                   check=True, capture_output=True)
    concat = seg_dir / "list.txt"
    lines_txt = []
    for sfile in segs:
        lines_txt.append(f"file '{sfile.name}'")
        lines_txt.append(f"file '{gap.name}'")
    concat.write_text("\n".join(lines_txt[:-1]), encoding="utf-8")
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
        "audio": "pod/latest.mp3", "hosts": ["Graham", "Emmy"],
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
