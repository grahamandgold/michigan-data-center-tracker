#!/usr/bin/env python3
"""doc_extract — the document desk's extraction stack, hardened.

Ladder (each rung only fires when the one above it comes up short):

  1. Plain fetch (urllib)  — fast path, works for simple township sites.
  2. Playwright render     — for JS portals (Granicus, CivicPlus, BoardDocs,
                             iCompass, Legistar, Municode). Renders the page,
                             harvests packet/agenda links out of the live DOM,
                             and screenshots the page as a vision fallback.
  3. pypdf text            — normal digital PDFs.
  4. Vision OCR            — scanned/image PDFs: render pages with pypdfium2
                             and have a vision model read them.

Also provides depth_score(): an honest 0-10 measure of how much real document
material we extracted, so the agenda desk can say "thin — needs human
background" instead of pretending.

Dependencies (workflow installs): pypdf, and optionally playwright+chromium,
pypdfium2. Everything degrades gracefully when a dependency is missing.
"""
from __future__ import annotations

import html as htmllib
import io
import re
import urllib.request
from urllib.parse import urljoin, urlparse

UA = {"User-Agent": "Mozilla/5.0 (Michigan Data Center Tracker agenda desk)"}

PORTAL_HOSTS = ("granicus.com", "civicplus.com", "civicclerk.com", "boarddocs.com",
                "icompass", "legistar.com", "municode.com", "civicweb.net",
                "primegov.com", "novusagenda.com", "escribemeetings.com")

DOC_WORDS = ("agenda", "packet", "staff report", "site plan", "minutes", "resolution",
             "ordinance", "downloadfile", "viewfile", "documentcenter", "attachment",
             "exhibit", "meetingpacket", "agendapacket")


def is_portal(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(p in host for p in PORTAL_HOSTS)


# ---------------------------------------------------------------- rung 1: plain fetch
def fetch(url: str, limit: int = 8_000_000, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limit)


def html_text(raw: bytes) -> str:
    s = raw.decode("utf-8", "ignore")
    s = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = htmllib.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\s+", " ", s).strip()


def find_doc_links(raw: bytes, base_url: str) -> list[tuple[str, str]]:
    """(url, link_text) pairs for likely packet documents in raw HTML."""
    s = raw.decode("utf-8", "ignore")
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', s, flags=re.S | re.I):
        href, text = m.group(1), re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip()
        full = urljoin(base_url, htmllib.unescape(href))
        if full in seen or full.startswith(("mailto:", "javascript:")):
            continue
        lower = (full + " " + text).lower()
        if full.lower().split("?")[0].endswith(".pdf") or any(k in lower for k in DOC_WORDS):
            seen.add(full)
            out.append((full, text[:80]))
    return out[:12]


# ---------------------------------------------------------------- rung 2: playwright
def render_page(url: str) -> tuple[str, list[tuple[str, str]], bytes | None]:
    """Render a JS portal page. Returns (visible_text, doc_links, screenshot_png).
    Returns ("", [], None) if Playwright isn't installed or the render fails."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("::warning::playwright not installed — portal page gets plain fetch only")
        return "", [], None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page(user_agent=UA["User-Agent"])
            page.goto(url, wait_until="networkidle", timeout=45_000)
            page.wait_for_timeout(1_500)
            # expand common accordion/agenda toggles so links become visible
            for sel in ("text=/agenda/i", "text=/packet/i", "text=/documents/i"):
                try:
                    for el in page.locator(sel).all()[:3]:
                        el.click(timeout=1_000)
                        page.wait_for_timeout(400)
                except Exception:  # noqa: BLE001
                    pass
            text = re.sub(r"\s+", " ", page.inner_text("body"))[:20_000]
            links, seen = [], set()
            for a in page.locator("a[href]").all()[:400]:
                try:
                    href = a.get_attribute("href") or ""
                    label = (a.inner_text() or "").strip()[:80]
                except Exception:  # noqa: BLE001
                    continue
                full = urljoin(url, href)
                lower = (full + " " + label).lower()
                if full in seen or full.startswith(("mailto:", "javascript:")):
                    continue
                if full.lower().split("?")[0].endswith(".pdf") or any(k in lower for k in DOC_WORDS):
                    seen.add(full)
                    links.append((full, label))
            shot = page.screenshot(full_page=True)
            browser.close()
            return text, links[:12], shot
    except Exception as e:  # noqa: BLE001
        print(f"::warning::playwright render failed for {url}: {e}")
        return "", [], None


# ---------------------------------------------------------------- rungs 3+4: PDFs
def pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages[:40]]
        return re.sub(r"\s+", " ", " ".join(pages)).strip()
    except Exception as e:  # noqa: BLE001
        print(f"::warning::pypdf extract failed: {e}")
        return ""


def pdf_page_images(data: bytes, max_pages: int = 6) -> list[bytes]:
    """Render PDF pages to PNG bytes for vision OCR (scanned documents)."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return []
    try:
        pdf = pdfium.PdfDocument(io.BytesIO(data))
        images = []
        for i in range(min(len(pdf), max_pages)):
            bitmap = pdf[i].render(scale=2.0)
            pil = bitmap.to_pil()
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            images.append(buf.getvalue())
        return images
    except Exception as e:  # noqa: BLE001
        print(f"::warning::pdf render failed: {e}")
        return []


def pdf_text_with_vision(data: bytes) -> str:
    """pypdf first; if the PDF is scanned (no text layer), vision-read it."""
    text = pdf_text(data)
    if len(text) > 300:
        return text
    images = pdf_page_images(data)
    if not images:
        return text
    import multi_ai_client as ai
    read = ai.vision("vision",
                     "Transcribe every piece of text in these government meeting document "
                     "pages, in reading order. Include agenda item numbers, parcel numbers, "
                     "dollar figures, acreage, megawatts, names and titles. Output plain text "
                     "only — no commentary.", images)
    if read:
        print(f"    vision OCR recovered {len(read)} chars from scanned PDF")
        return re.sub(r"\s+", " ", read).strip()
    return text


# ---------------------------------------------------------------- the dossier
def build_dossier(url: str, body_name: str = "") -> tuple[str, list[dict], dict]:
    """Full extraction ladder for one meeting agenda URL.

    Returns (dossier_text, documents_read, meta) where meta carries
    {"depth_score": 0-10, "thin": bool, "method": "..."}.
    """
    parts: list[tuple[str, str]] = []
    docs: list[dict] = []
    method = "plain"
    screenshot = None

    raw = b""
    try:
        raw = fetch(url)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::plain fetch failed {url}: {e}")

    if url.lower().split("?")[0].endswith(".pdf") and raw[:4] == b"%PDF":
        parts.append(("AGENDA PDF", pdf_text_with_vision(raw)))
        docs.append({"label": "Agenda (PDF)", "url": url})
        links: list[tuple[str, str]] = []
    else:
        page_text = html_text(raw) if raw else ""
        links = find_doc_links(raw, url) if raw else []
        # Escalate to Playwright when the page looks JS-rendered or is a known portal
        if is_portal(url) or len(page_text) < 400 or not links:
            rtext, rlinks, screenshot = render_page(url)
            if rtext:
                method = "playwright"
                page_text = rtext if len(rtext) > len(page_text) else page_text
                merged = {u: l for u, l in links}
                merged.update({u: l for u, l in rlinks})
                links = list(merged.items())[:12]
        if page_text:
            parts.append(("AGENDA PAGE", page_text[:8000]))
            docs.append({"label": "Agenda page", "url": url})

    grabbed = 0
    for purl, label in links:
        if grabbed >= 4:
            break
        try:
            data = fetch(purl)
        except Exception as e:  # noqa: BLE001
            print(f"    skip {purl[-60:]}: {e}")
            continue
        if data[:4] != b"%PDF":
            continue
        text = pdf_text_with_vision(data)
        if len(text) > 200:
            nice = label or purl.rsplit("/", 1)[-1]
            parts.append((f"DOCUMENT: {nice}", text[:14000]))
            docs.append({"label": nice[:70], "url": purl})
            grabbed += 1
            print(f"    read PDF: {nice[:60]} ({len(text)} chars)")

    # Last resort: nothing extractable but we have a screenshot — vision-read it
    if grabbed == 0 and screenshot and sum(len(t) for _, t in parts) < 500:
        import multi_ai_client as ai
        read = ai.vision("vision",
                         f"This is a screenshot of the {body_name or 'government'} meeting "
                         "agenda page. Transcribe the agenda items, dates, and any document "
                         "titles you can read. Plain text only.", [screenshot])
        if read:
            method = "vision-screenshot"
            parts.append(("AGENDA (vision-read from rendered page)", read[:8000]))

    dossier = "\n\n".join(f"===== {label} =====\n{text}" for label, text in parts if text)[:36000]
    meta = _score(dossier, grabbed, method)
    return dossier, docs, meta


def depth_score(dossier: str, pdfs_read: int) -> int:
    """0-10: how much real document material do we actually have?"""
    chars = len(dossier)
    score = 0
    score += min(4, pdfs_read * 2)                       # packet PDFs are the gold
    score += 2 if chars > 4000 else (1 if chars > 1200 else 0)
    signals = sum(1 for w in ("parcel", "acre", "megawatt", " mw", "tax", "abatement",
                              "moratorium", "site plan", "resolution", "ordinance",
                              "special use", "rezoning", "$")
                  if w in dossier.lower())
    score += min(4, signals)
    return min(10, score)


def _score(dossier: str, pdfs_read: int, method: str) -> dict:
    s = depth_score(dossier, pdfs_read)
    return {"depth_score": s, "thin": s < 6, "method": method, "pdfs_read": pdfs_read}
