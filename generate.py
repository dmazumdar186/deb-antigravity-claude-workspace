"""Phase 2: GLM 5.2 creative-slice generator for the yoga_jitendra_site.

Calls GLM 5.2 (z-ai/glm-5.2 via OpenRouter) via the workspace's canonical
`call_model` wrapper. Every prompt is design-only — no PII, no reviewer
names, no phone number. Per ~/.claude/rules/model-tier.md Exhibit C.

Currently generates one creative slice:
    - HeroBackdrop.astro : subtle SVG mandala breath animation, positioned
      as a decorative backdrop behind the Hero copy.

Run from workspace root:
    py execution/personal_workflows/yoga_jitendra_site/generate.py

Cost: ~EUR 0.03 per call. Hard-caps: 2 rounds per slice.
"""

from __future__ import annotations
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WORKSPACE))

from execution.modules.model_router import call_model  # noqa: E402

SITE_DIR = WORKSPACE / "execution" / "personal_workflows" / "yoga_jitendra_site"
COMPONENTS_DIR = SITE_DIR / "src" / "components"


DESIGN_BRIEF = """
DESIGN SYSTEM — Hatha Yoga marketing page, Paris.
Palette:
  cream       #F4EDE1  (background)
  cream-100   #FBF7EE  (soft surface)
  sand        #D9C7A7
  terracotta  #C9744A  (accent, CTAs)
  sage        #6B7A5A  (secondary accent, botanical)
  ink         #2E2A26  (body text)
Typography: Fraunces (serif) for display, Inter for body.
Mood: warm, earthen, contemplative. Traditional yoga — not fitness-y. Not
      generic wellness. Think Elena Brower / early Iyengar posters.
Motion rule: subtle only. Every animation MUST respect
      `@media (prefers-reduced-motion: reduce)` and stop.
"""


HERO_BACKDROP_PROMPT = """
Generate a single Astro component file named `HeroBackdrop.astro` that renders a
DECORATIVE, MOTION-SUBTLE, INLINE-SVG mandala breath animation, intended to sit
BEHIND the hero copy of a yoga teacher's homepage.

REQUIREMENTS (hard):
1. One file. Contents are: Astro frontmatter (`---` ... `---`, may be empty), an
   inline `<svg>` element, and a `<style>` block. NO client-side JavaScript, NO
   imports, NO external assets, NO images, NO web fonts. CSS animation only.
2. Absolutely no text characters visible in the SVG. Pure geometry.
3. Root layout: the component renders one `<div class="hero-backdrop">` wrapping
   the `<svg>`. The wrapper must use `position: absolute; inset: 0; z-index: 0;
   overflow: hidden; pointer-events: none;` and be `aria-hidden="true"`.
4. Mandala geometry: use `<circle>`, `<path>`, and `<g>` — NO `<image>`. A center
   circle + 8 or 12 rotationally-symmetric petals + one or two outer rings. Line
   strokes only, no heavy fills. Use `currentColor` OR the design-system colors
   (see palette) at ~14-22% opacity so it stays subtle behind text.
5. Motion (all CSS only):
     - Center: slow scale breath (min 4s per full breath cycle) between 0.94x
       and 1.06x. Infinite.
     - Whole mandala: rotate at 60-90 seconds per full turn. Infinite.
     - Outer rings: opacity shimmer between 0.10 and 0.22, ~10s cycle.
   All three animations MUST stop under `@media (prefers-reduced-motion:
   reduce)` (opacity fixed at midpoint, transforms cleared).
6. Colors: prefer using CSS variables `var(--terracotta)`, `var(--sage)`,
   `var(--sand)` (already defined at :root by the site's global.css). Fall back
   to the palette hex codes if variables aren't available.
7. Size: SVG must be `viewBox` based (not fixed pixels). Set the SVG element to
   `width: min(85vmin, 720px); height: auto; position: absolute; top: 50%;
   right: -8vmin; transform: translateY(-50%);` — i.e. anchored to the right
   edge of the hero container, offset off-screen slightly so it feels like it's
   emerging from behind the photo column.
8. Everything is scoped to `.hero-backdrop` in the `<style>` block so it can't
   leak. Use Astro's `<style>` (NOT `<style is:global>`).
9. Total output MUST be a single ```astro code fence containing the whole file.
   Nothing before or after the fence. Do not explain.

DESIGN SYSTEM CONTEXT (for taste):
""" + DESIGN_BRIEF


def _extract_astro(text: str) -> str:
    """Extract the first ```astro (or ```html) fenced code block, else return text."""
    for lang in ("astro", "html", "svg"):
        m = re.search(r"```" + lang + r"\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
    # Fallback: first ``` block, whatever the language tag
    m = re.search(r"```\w*\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _validate_hero_backdrop(code: str) -> tuple[bool, list[str]]:
    """Quick static checks on the GLM output. Returns (ok, reasons)."""
    reasons = []
    if "<svg" not in code:
        reasons.append("no <svg> tag")
    if "hero-backdrop" not in code:
        reasons.append("no .hero-backdrop class")
    if "<script" in code:
        reasons.append("contains <script> — not allowed")
    if "<img" in code or "url(" in code:
        reasons.append("contains external asset reference — not allowed")
    if "prefers-reduced-motion" not in code:
        reasons.append("missing prefers-reduced-motion")
    if "aria-hidden" not in code:
        reasons.append("missing aria-hidden")
    if len(code) < 400:
        reasons.append(f"suspiciously short ({len(code)} chars)")
    if len(code) > 12000:
        reasons.append(f"suspiciously long ({len(code)} chars)")
    return (len(reasons) == 0, reasons)


def generate_hero_backdrop(max_rounds: int = 2) -> Path:
    """Call GLM 5.2 up to max_rounds times to produce a valid HeroBackdrop.astro."""
    out_path = COMPONENTS_DIR / "HeroBackdrop.astro"
    system = (
        "You are a senior creative front-end engineer with strong taste in "
        "Indian and modern design. You output ONLY the requested file, in a "
        "single fenced code block. No prose, no explanation, no README."
    )
    last_reasons = []
    for attempt in range(1, max_rounds + 1):
        print(f"[generate.py] GLM 5.2 attempt {attempt}/{max_rounds}...", flush=True)
        user = HERO_BACKDROP_PROMPT
        if attempt > 1 and last_reasons:
            user += (
                "\n\nPREVIOUS ATTEMPT FAILED VALIDATION — reasons: "
                + "; ".join(last_reasons)
                + ". Fix ALL of these in the next attempt."
            )
        try:
            result = call_model(
                "glm",
                system=system,
                user=user,
                max_tokens=6000,
                sensitivity="public",
            )
        except Exception as exc:
            print(f"[generate.py] call_model raised: {exc!r}", flush=True)
            last_reasons = [f"call_model raised: {exc!r}"]
            continue

        raw = result.get("text", "") if isinstance(result, dict) else str(result)
        code = _extract_astro(raw)
        ok, reasons = _validate_hero_backdrop(code)
        print(f"[generate.py] validation: ok={ok} reasons={reasons}", flush=True)
        if ok:
            out_path.write_text(code + "\n", encoding="utf-8")
            print(f"[generate.py] wrote {out_path} ({len(code)} chars)", flush=True)
            return out_path
        last_reasons = reasons

    # Hard-cap reached: hand-write a minimal fallback and continue.
    fallback = _hand_written_fallback()
    out_path.write_text(fallback, encoding="utf-8")
    print(
        f"[generate.py] HARD-CAP HIT after {max_rounds} GLM attempts. Wrote "
        f"hand-written fallback ({len(fallback)} chars). Last reasons: {last_reasons}",
        flush=True,
    )
    return out_path


def _hand_written_fallback() -> str:
    """Minimal hand-authored mandala backdrop — used if GLM output fails validation twice."""
    return """---
---
<div class="hero-backdrop" aria-hidden="true">
  <svg viewBox="-100 -100 200 200" xmlns="http://www.w3.org/2000/svg">
    <g class="mandala">
      <circle class="ring outer" cx="0" cy="0" r="90" />
      <circle class="ring mid"   cx="0" cy="0" r="70" />
      <g class="petals">
        {[...Array(12)].map((_, i) => (
          <ellipse cx="0" cy="-55" rx="6" ry="30" transform={`rotate(${i * 30})`} />
        ))}
      </g>
      <circle class="core" cx="0" cy="0" r="14" />
    </g>
  </svg>
</div>
<style>
  .hero-backdrop {
    position: absolute; inset: 0; z-index: 0; overflow: hidden; pointer-events: none;
  }
  .hero-backdrop svg {
    width: min(85vmin, 720px); height: auto;
    position: absolute; top: 50%; right: -8vmin; transform: translateY(-50%);
    color: var(--terracotta, #C9744A);
    opacity: 0.22;
  }
  .mandala { animation: hb-rotate 75s linear infinite; transform-origin: 0 0; }
  .ring    { fill: none; stroke: currentColor; stroke-width: 0.6; opacity: 0.18; animation: hb-shimmer 10s ease-in-out infinite; }
  .mid     { opacity: 0.14; animation-delay: -3s; }
  .petals  ellipse { fill: currentColor; opacity: 0.12; }
  .core    { fill: currentColor; opacity: 0.55; animation: hb-breathe 6s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }
  @keyframes hb-rotate  { to { transform: rotate(360deg); } }
  @keyframes hb-breathe { 0%,100% { transform: scale(0.94); opacity: 0.45; } 50% { transform: scale(1.06); opacity: 0.7; } }
  @keyframes hb-shimmer { 0%,100% { opacity: 0.10; } 50% { opacity: 0.22; } }
  @media (prefers-reduced-motion: reduce) {
    .mandala, .core, .ring { animation: none !important; transform: none !important; opacity: 0.16 !important; }
  }
</style>
"""


if __name__ == "__main__":
    generate_hero_backdrop(max_rounds=2)
