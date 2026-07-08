"""Output-acceptance gate for yoga_jitendra_site.

Hard-fails if any user-facing artifact is structurally broken, if PII or
placeholder tokens leaked, or if removed collages still appear.

Run from workspace root:
    py tests/acceptance_yoga_jitendra.py
Exit code 0 = gate green; non-zero = block the deploy.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
DIST_HTML = (
    WORKSPACE
    / "execution"
    / "personal_workflows"
    / "yoga_jitendra_site"
    / "dist"
    / "index.html"
)

REQUIRED_FR = [
    ("hero eyebrow FR",          "Hatha Yoga"),
    ("hero headline FR word 1",  "Respirer"),
    ("hero headline FR word 2",  "Bouger"),
    ("hero headline FR word 3",  "déposer"),
    ("about section FR",         "Le professeur"),
    ("lineage eyebrow FR",       "La tradition"),
    ("lineage phrase FR",        "rishis"),
    ("book cta label FR",        "Réserver"),
    ("testimonials FR",          "Ce qu&#39;en disent"),
]

REQUIRED_EN = [
    ("hero headline EN word 1",  "Breathe"),
    ("hero headline EN word 2",  "Move"),
    ("hero headline EN word 3",  "Land"),
    ("about section EN",         "About the teacher"),
    ("lineage eyebrow EN",       "The lineage"),
    ("book cta EN",              ">Book<"),
]

REQUIRED_SANSKRIT = [
    ("shloka Devanagari",  "योगश्चित्तवृत्तिनिरोधः"),
    ("shloka translit",    "Yogaḥ"),
    ("shloka source",      "Patañjali"),
    ("Om symbol",          "ॐ"),
    ("Ashtanga limb 1",    "Yama"),
    ("Ashtanga limb 3",    "Āsana"),
    ("Ashtanga limb 4",    "Prāṇāyāma"),
    ("Ashtanga limb 8",    "Samādhi"),
]

REQUIRED_CONTRACT = [
    ("WhatsApp CTA",         "wa.me/33758255583"),
    ("phone tel link",       "tel:+33758255583"),
    ("email mailto link",    "jitendranitrr13@gmail.com"),
    ("studio address",       "22 rue Eugène Manuel"),
    ("hero backdrop",        "hero-backdrop"),
    ("mandala rotation",     "mandala-spin"),
    # Audio: real vocal Om chant recording (replaces formant-synth playOm/playFluteNote as of 2026-07-08).
    ("om audio element",     'id="om-audio"'),
    ("om chant asset",       "om-aum-chant.mp3"),
    ("tanpura JS",           "buildDrone"),
    ("first-gesture auto",   "firstGesture"),
    ("audio mute button",    "data-audio-toggle"),
    # No pricing anywhere on site (Jitendra's rule, 2026-07-08).
    ("all offerings on quote",  "Sur devis"),
    # Lineage yantra backdrop (2026-07-08).
    ("lineage yantra backdrop", "lineage-yantra-bg"),
    # Footer credit link (Debanjan + ProdCraft, 2026-07-08).
    ("footer designer credit FR", "Conçu par Debanjan"),
    ("footer designer credit EN", "Designed by Debanjan"),
    ("footer prodcraft link",     "prodcraft.fyi"),
    # Enterprise-tile video (Jitendra's group session, 2026-07-08).
    ("enterprise video",     "enterprise-yoga.mp4"),
    # Open-air-tile crossfade (2026-07-08).
    ("crossfade markup",     "data-crossfade"),
    ("crossfade active flag","is-active"),
]

REQUIRED_ASSETS = [
    ("hero image",             "champ-de-mars-eiffel"),
    ("portrait image",         "portrait-namaste"),
    ("teaching image",         "teaching-backbend"),
    ("meditation image",       "meditation-portrait"),
    # New studio image (Jitendra's class in Dhanurasana, added 2026-07-08).
    ("studio class image",     "studio-jitendra-class.jpg"),
]

BANNED_STRINGS = [
    ("no placeholder tokens",             "{{"),
    ("no removed gallery montsouris",     "gallery-montsouris"),
    ("no removed gallery interiors",      "gallery-studio-interiors"),
    # No pricing anywhere on site (client rule, 2026-07-08).
    ("no priceRange in schema",           '"priceRange"'),
    ("no euro-price literal",             "60 €"),
    ("no dollar-price literal",           "€60"),
    ("no dead formant-Om code",           "playOm"),
    ("no dead flute code",                "playFluteNote"),
    # ProdCraft + Debanjan are now INTENTIONAL in the footer credit — removed from banned.
]


@dataclass
class Findings:
    errors: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.errors.append(msg)


def main() -> int:
    if not DIST_HTML.exists():
        print(f"FATAL: {DIST_HTML} does not exist. Run `npm run build` first.")
        return 2

    html = DIST_HTML.read_text(encoding="utf-8")
    f = Findings()

    for label, needle in REQUIRED_FR + REQUIRED_EN + REQUIRED_SANSKRIT + REQUIRED_CONTRACT + REQUIRED_ASSETS:
        if needle not in html:
            f.fail(f"MISSING [{label}]: '{needle}'")

    for label, needle in BANNED_STRINGS:
        if needle in html:
            f.fail(f"LEAKED [{label}]: '{needle}' present in built HTML")

    if f.errors:
        print(f"FAIL: {len(f.errors)} blocking issue(s):")
        for e in f.errors:
            print(f"  - {e}")
        return 1

    total = (
        len(REQUIRED_FR)
        + len(REQUIRED_EN)
        + len(REQUIRED_SANSKRIT)
        + len(REQUIRED_CONTRACT)
        + len(REQUIRED_ASSETS)
        + len(BANNED_STRINGS)
    )
    print(f"PASS: yoga_jitendra acceptance gate green — {total} assertions verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
