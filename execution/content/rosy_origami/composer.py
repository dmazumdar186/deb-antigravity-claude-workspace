"""LLM composer — generates per-section text with source-pinning and voice match.

V0 voice strategy: inline the voice profile examples into the Gemini prompt directly.
The plan's Phase 0f originally specified a humanizer subprocess pass on top, but the
inlined-prompt approach hit a sufficient voice quality bar in user review and was
accepted as the V0 path. Humanizer subprocess wiring remains a future enhancement
(call_humanizer scaffold exists in generate_demo.py for the upgrade).

Model: gemini-2.5-flash-lite. The plan originally specified gemini-2.0-flash but that
exact model name returned quota=0 for this API key while 2.5-flash-lite worked on the
free tier. Both are Gemini Flash-class; flash-lite has equivalent rate limits for our
use case (<10 calls per newsletter).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

# Free tier: 5 RPM on gemini-2.5-flash. Sleep between calls to stay under.
# Set ROSY_GEMINI_SLEEP=0 to disable for paid/higher-tier keys.
_INTER_CALL_SLEEP = float(os.environ.get("ROSY_GEMINI_SLEEP", "13"))
_last_call_ts = 0.0


def _throttle() -> None:
    global _last_call_ts
    elapsed = time.monotonic() - _last_call_ts
    if elapsed < _INTER_CALL_SLEEP:
        wait = _INTER_CALL_SLEEP - elapsed
        print(f"  [throttle] sleeping {wait:.1f}s to stay under 5 RPM", file=sys.stderr)
        time.sleep(wait)
    _last_call_ts = time.monotonic()


# ---------------------------------------------------------------------------
# Per-section language guard (eval-first.md)
# ---------------------------------------------------------------------------

# Minimum length before langdetect output is reliable. Sections shorter than
# this (e.g. very brief closings) skip the check rather than firing false
# positives on coin-flip detection.
_MIN_LANGDETECT_CHARS = 30

# Langdetect ambiguity pairs commonly seen on borderline FR/EN/CA text.
_LANG_EQUIV = {("en", "ca"), ("ca", "en"), ("fr", "ca"), ("ca", "fr")}


def check_section_language(
    section_name: str,
    text: str,
    allowed_langs: list[str] | None,
) -> tuple[bool, str | None]:
    """Verify a composed section's detected language is in `allowed_langs`.

    Returns (ok, message). `ok` is True when the section is acceptable or
    when there isn't enough signal to judge (short text, detection error,
    no allowed_langs configured). The message is a one-line diagnostic
    suitable for stderr; None when ok.
    """
    if not allowed_langs:
        return True, None
    if not text or len(text.strip()) < _MIN_LANGDETECT_CHARS:
        return True, None
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        detected = detect(text)
    except Exception:
        # LangDetectException or anything else: skip rather than fail the run.
        return True, None
    if detected in allowed_langs:
        return True, None
    for cand in allowed_langs:
        if (detected, cand) in _LANG_EQUIV:
            return True, None
    return False, (
        f"[lang-guard] section {section_name!r} detected as {detected!r}; "
        f"tenant allows {allowed_langs}"
    )

ROOT = Path(__file__).resolve().parents[3]
VOICES_DIR = ROOT / "execution" / "content" / "voices"

MODEL = "gemini-2.5-flash"


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if k.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v


def _voice_block(voice_name: str) -> str:
    path = VOICES_DIR / f"{voice_name}.json"
    voice = json.loads(path.read_text(encoding="utf-8"))
    lines = [f"## Voice profile: {voice['display_name']}", ""]
    lines.append(f"Register: {voice['traits']['register']}")
    lines.append(f"Sentence length: {voice['traits']['sentence_length']}")
    lines.append(f"Formatting habits: {voice['traits']['formatting']}")
    lines.append("")
    lines.append("Phrases this voice USES naturally: " + ", ".join(voice["lexicon"]["uses"][:10]))
    lines.append("Phrases this voice AVOIDS: " + ", ".join(voice["lexicon"]["avoids"][:10]))
    lines.append("")
    lines.append("Sample posts in this voice (mimic cadence, NOT content):")
    for i, ex in enumerate(voice["examples"][:6], 1):
        lines.append(f"  Sample {i}: {ex[:300]}")
    return "\n".join(lines)


_SIGNOFF_PATTERNS = [
    r"^\s*[-–—]\s*GIO\s*(Team)?\s*$",
    r"^\s*GIO\s+Team\s*$",
    r"^\s*[💜❤️🧡💛💚🩵💙💗💓💕]+\s*[-–—]?\s*GIO.*$",
    r"^\s*[💜❤️🧡💛💚🩵💙💗💓💕✨🌾🔥]{1,3}\s*$",  # bare emoji line
]

_HASHTAG_LINE = re.compile(r"^\s*(#\w[\w-]*\s*){2,}$")  # 2+ hashtags in a row = hashtag block


def _strip_signoff_lines(text: str) -> str:
    """Remove trailing sign-off lines AND hashtag-block lines (in non-closing sections)."""
    lines = text.splitlines()
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if any(re.match(p, last, re.IGNORECASE) for p in _SIGNOFF_PATTERNS):
            lines.pop()
            continue
        if _HASHTAG_LINE.match(last):
            lines.pop()
            continue
        break
    # Also strip any hashtag-block line that sits anywhere (LLM sometimes adds mid-text)
    lines = [ln for ln in lines if not _HASHTAG_LINE.match(ln.strip())]
    return "\n".join(lines).strip()


def classify_event_section(rendered_chunks: list[str]) -> str:
    """Decide section title based on how the LLM classified each chunk.

    Chunks starting with '### Save the Date' or '### Coming up' are teasers.
    All others are recaps/greetings.
    Returns one of: 'Event Recap', 'What's Coming Up', 'Community Updates'.
    """
    teaser_count = sum(
        1 for c in rendered_chunks
        if re.match(r"###\s*(save the date|coming up)", c.strip(), re.IGNORECASE)
    )
    total = len(rendered_chunks)
    if total == 0:
        return "Community Updates"
    if teaser_count == total:
        return "What's Coming Up"
    if teaser_count == 0:
        return "Event Recap"
    return "Community Updates"


def _client() -> genai.Client:
    _load_env()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY not in environment (.env or shell). Cannot proceed.")
    return genai.Client(api_key=key)


def compose_intro(theme: str, voice: str, client: genai.Client) -> str:
    voice_block = _voice_block(voice)
    prompt = f"""{voice_block}

## Your task

Write the INTRO paragraph for this month's community newsletter.

HARD CONSTRAINTS:
- 50-70 words. ONE paragraph. NO sub-headers.
- DO NOT open with "Hello everyone", "Hello friends", "Dear members", "We hope you enjoy",
  "We're so pleased to bring you", "This month we're reflecting on", or any generic
  newsletter-host opener. The voice samples above NEVER open that way.
- Open EITHER with: (a) ✨ + the theme phrase verbatim, OR (b) a punchy hook sentence
  about one concrete thing from the theme, in the GIO cadence (e.g., "What a season of...",
  "Color, music, and our community came together this month...").
- 'we' / 'our' framing throughout.
- Match the voice samples in punctuation, emoji habits, sentence length.
- Use ONLY the theme below. Do NOT invent events, people, dates not in the theme.

Theme: {theme}

Return ONLY the intro paragraph. No "Intro:", no markdown headers, no explanation."""
    _throttle()
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=300),
    )
    return _strip_signoff_lines((resp.text or "").strip())


def compose_event_recap(source_caption: str, source_url: str, voice: str,
                        client: genai.Client, today_iso: str | None = None) -> str:
    voice_block = _voice_block(voice)
    today_note = f"\nToday's date: {today_iso}." if today_iso else ""
    prompt = f"""{voice_block}

## Your task

Generate a NEWSLETTER SECTION about this Instagram post. CRITICAL: classify the post FIRST.{today_note}

CLASSIFY THE SOURCE:
- (A) RECAP — source explicitly describes a past event in past tense ("thank you to everyone
  who came", "winners are", "what a fantastic evening", "highlights from"). It HAS post-event
  detail.
- (B) TEASER — source is a pre-event announcement (Save the Date, "join us on [future date]",
  "register now", prize draw not yet happened). It has NO post-event facts.
- (C) GREETING — source is a festival/awareness-day greeting with no event component.

THEN WRITE based on classification:

If (A) RECAP: write a 70-100 word recap.
  FIRST LINE: `### <Event Name>`.
  BODY: lead with what happened + one concrete outcome from the source (winner names,
  attendee vibe, etc. — ONLY if explicitly in source). End with one line on what the
  community took from it.

If (B) TEASER: write a 60-90 word UPCOMING-EVENT teaser (not a recap).
  FIRST LINE: `### Coming up: <Event Name>` or `### Save the Date: <Event Name>`.
  BODY: include the future date, venue, and registration CTA from the source verbatim.
  Use present/future tense ("We're inviting you to...", "Join us on...").
  DO NOT write as if it has happened.

If (C) GREETING: write a 50-70 word reflection.
  FIRST LINE: `### <Greeting/Theme>` (e.g. "### Happy Women's Day").
  BODY: a short reflection in the voice — DO NOT invent event details.

HARD CONSTRAINTS ALL TYPES:
- Match the voice samples in cadence, emoji habits, punctuation.
- Do NOT invent dates, names, attendee counts, outcomes, or details NOT in the source.
- Do NOT copy the source verbatim — paraphrase.
- Do NOT include the source's hashtag block.
- Do NOT add a sign-off line.

Source post (Instagram, @giofranceparis):
{source_caption}

Source URL: {source_url}

Return ONLY the `###` heading line followed by the body. No explanation, no "Classification: A/B/C" label."""
    _throttle()
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.5, max_output_tokens=450),
    )
    return _strip_signoff_lines((resp.text or "").strip())


def compose_news_roundup(items: list[dict], voice: str, client: genai.Client) -> str:
    """items: list of {title, body, url, source_name}."""
    voice_block = _voice_block(voice)
    sources_block = "\n\n".join(
        f"[{i+1}] {it['title']}\nSource: {it.get('source_name','')}\nURL: {it['url']}\n\n{it['body'][:600]}"
        for i, it in enumerate(items)
    )
    prompt = f"""{voice_block}

## Your task

Write a NEWS ROUNDUP section summarising recent news relevant to our community
(Indian diaspora in France / Paris). Draw ONLY from the sources below.

HARD CONSTRAINTS:
- For EACH source, write ONE short bullet: 25-40 words.
- Format: `- **<short headline>** — <one-sentence summary>. ([Source](<url>))`
- Use ONLY facts from the source body. Do NOT invent dates, numbers, names, places.
- Skip any source that is irrelevant to Indian community in France/Paris.
- Match the voice samples — warm but informative.
- NO sign-off line. NO hashtag block.

Sources:
{sources_block}

Return ONLY the bullet list (use markdown `-` bullets). No header line."""
    _throttle()
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.4, max_output_tokens=600),
    )
    return _strip_signoff_lines((resp.text or "").strip())


def compose_closing(cta: str, voice: str, client: genai.Client) -> str:
    voice_block = _voice_block(voice)
    prompt = f"""{voice_block}

## Your task

Write the CLOSING paragraph for this month's community newsletter.

HARD CONSTRAINTS:
- 35-55 words. ONE short paragraph.
- DO NOT use these patterns or any close variant:
  • "your engagement makes our work / events / community shine / special"
  • "we hope you enjoyed", "we look forward to hearing from you"
  • "thank you for being a vital part of"
  • "let's continue to" / "let's keep"
  These are newsletter cliches the voice samples never use.
- DO open with one concrete community-grounded line, then the CTA, then sign-off.
- CTA can be lightly rephrased, must be present.
- Sign-off: a warm emoji + "-GIO Team" pattern matching the voice samples (e.g., "💜 -GIO Team").
- Match the voice samples in cadence and warmth.

CTA: {cta}

Return ONLY the closing paragraph."""
    _throttle()
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=250),
    )
    return (resp.text or "").strip()


# Simple hallucination tripwire — flag dates/years that don't appear in any source
def find_hallucinated_dates(generated: str, sources: list[str]) -> list[str]:
    combined_source = " ".join(sources).lower()
    flagged = []
    # year/month/day patterns
    patterns = [
        r"\b20\d{2}\b",                             # years
        r"\b\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
        r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\b",
        r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
    ]
    for pat in patterns:
        for m in re.finditer(pat, generated, re.IGNORECASE):
            tok = m.group(0).lower()
            if tok not in combined_source:
                flagged.append(m.group(0))
    return flagged
