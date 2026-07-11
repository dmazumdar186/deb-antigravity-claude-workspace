"""Output-acceptance gate for yoga_jitendra_site (post i18n restructure).

Hard-fails if any user-facing artifact is structurally broken, if PII or
placeholder tokens leaked, if removed collages still appear, if hreflang /
canonical / sitemap SEO primitives are wrong, or if FR content leaks into
the /en/ page (or vice versa) after the 2026-07-11 i18n restructure.

Run from workspace root:
    py tests/acceptance_yoga_jitendra.py
Exit code 0 = gate green; non-zero = block the deploy.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
DIST = (
    WORKSPACE
    / "execution"
    / "personal_workflows"
    / "yoga_jitendra_site"
    / "dist"
)
FR_HTML = DIST / "index.html"
EN_HTML = DIST / "en" / "index.html"
MERCI_HTML = DIST / "merci" / "index.html"
THANKS_HTML = DIST / "en" / "thanks" / "index.html"
ROBOTS = DIST / "robots.txt"
SITEMAP_INDEX = DIST / "sitemap-index.xml"
SITEMAP_0 = DIST / "sitemap-0.xml"

# Content patterns that MUST appear on the FR home page.
REQUIRED_FR = [
    ("hero eyebrow FR",          "Hatha Yoga"),
    ("hero headline FR word 1",  "Respirer"),
    ("hero headline FR word 2",  "Bouger"),
    ("hero headline FR word 3",  "déposer"),
    ("about section FR",         "Le professeur"),
    ("lineage eyebrow FR",       "La tradition"),
    ("lineage phrase FR",        "rishis"),
    ("book cta label FR",        "Réserver"),
    ("testimonials FR",          "Ce qu"),  # Both apostrophe forms may appear
    ("footer designer credit FR", "Conçu par Debanjan"),
    # Corporate clients (added 2026-07-11 from TrainMe screenshot).
    ("corporate client label FR", "Ils m&#39;ont fait confiance"),
    ("client TotalEnergies",      "TotalEnergies"),
    ("client SEMMARIS",           "SEMMARIS"),
    ("client Emmaüs",             "Emmaüs Solidarité"),
]

# Content patterns that MUST appear on the EN home page.
REQUIRED_EN = [
    ("hero headline EN word 1",  "Breathe"),
    ("hero headline EN word 2",  "Move"),
    ("hero headline EN word 3",  "Land"),
    ("about section EN",         "About the teacher"),
    ("lineage eyebrow EN",       "The lineage"),
    ("book cta EN",              ">Book<"),
    ("footer designer credit EN", "Designed by Debanjan"),
    ("client label EN",           "Trusted by"),
]

# Shared markup that MUST appear on BOTH FR and EN home pages.
REQUIRED_BOTH = [
    ("WhatsApp CTA",         "wa.me/33758255583"),
    ("phone tel link",       "tel:+33758255583"),
    ("email mailto link",    "jitendranitrr13@gmail.com"),
    ("studio address",       "22 rue Eugène Manuel"),
    ("hero backdrop",        "hero-backdrop"),
    ("mandala rotation",     "mandala-spin"),
    ("ambient audio element", 'id="om-audio"'),
    ("birds ambient asset",   "birds-dawn.mp3"),
    ("first-gesture auto",    "firstGesture"),
    ("audio mute button",    "data-audio-toggle"),
    ("lineage yantra backdrop", "lineage-yantra-bg"),
    ("footer prodcraft link",     "prodcraft.fyi"),
    ("enterprise video",     "enterprise-yoga.mp4"),
    ("crossfade markup",     "data-crossfade"),
    ("crossfade active flag","is-active"),
]

# Sanskrit / Devanagari — appears in shared Lineage content (language-neutral).
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

REQUIRED_ASSETS = [
    ("portrait image",         "portrait-namaste"),
    ("teaching image",         "teaching-backbend"),
    ("meditation image",       "meditation-portrait"),
    ("studio class image",     "studio-jitendra-class.jpg"),
]

BANNED_STRINGS = [
    ("no placeholder tokens",             "{{"),
    ("no removed gallery montsouris",     "gallery-montsouris"),
    ("no removed gallery interiors",      "gallery-studio-interiors"),
    ("no priceRange in schema",           '"priceRange"'),
    ("no euro-price literal",             "60 €"),
    ("no dollar-price literal",           "€60"),
    ("no dead formant-Om code",           "playOm"),
    ("no dead flute code",                "playFluteNote"),
    # Post-i18n restructure: no leftover data-lang-content markup or JS toggle.
    ("no data-lang-content markup",       "data-lang-content"),
    ("no data-lang-switch button",        "data-lang-switch"),
    # No pages.dev URL leak (canonical must be the real domain).
    ("no pages.dev URL leak",             "yoga-jitendra.pages.dev"),
]

# FR-only strings that must NOT appear in the EN page (no cross-language leak).
FR_ONLY_MUST_NOT_APPEAR_IN_EN = [
    "Respirer",
    "Bouger",
    "Le professeur",
    "Conçu par Debanjan",
    "Ils m&#39;ont fait confiance",
]

# EN-only strings that must NOT appear in the FR page.
EN_ONLY_MUST_NOT_APPEAR_IN_FR = [
    "Breathe",
    "About the teacher",
    "Designed by Debanjan",
    "Trusted by",
]


@dataclass
class Findings:
    errors: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.errors.append(msg)


def check_seo_primitives(fr_html: str, en_html: str, f: Findings) -> None:
    """Assert reciprocal hreflang triplet + correct canonical + correct <html lang> per route."""
    # FR page checks
    if 'lang="fr"' not in fr_html[:200]:
        f.fail("FR page missing <html lang='fr'> declaration")
    if 'rel="canonical" href="https://yogaavecjitendra.fr/"' not in fr_html:
        f.fail("FR page canonical wrong or missing")
    for hl in ("fr", "en", "x-default"):
        if f'hreflang="{hl}"' not in fr_html:
            f.fail(f"FR page missing hreflang='{hl}' tag")

    # EN page checks
    if 'lang="en"' not in en_html[:200]:
        f.fail("EN page missing <html lang='en'> declaration")
    if 'rel="canonical" href="https://yogaavecjitendra.fr/en/"' not in en_html:
        f.fail("EN page canonical wrong or missing")
    for hl in ("fr", "en", "x-default"):
        if f'hreflang="{hl}"' not in en_html:
            f.fail(f"EN page missing hreflang='{hl}' tag")

    # LCP preload must point at real hero (meditation-portrait, not the removed champ-de-mars-eiffel as hero)
    for label, html in (("FR", fr_html), ("EN", en_html)):
        m = re.search(r'rel="preload"[^>]*href="([^"]*)"', html)
        if not m:
            f.fail(f"{label} page missing LCP preload")
        elif "meditation-portrait" not in m.group(1):
            f.fail(f"{label} page LCP preload points at wrong image: {m.group(1)}")


def check_schema_org(fr_html: str, en_html: str, f: Findings) -> None:
    """Assert LocalBusiness + Person + 4 Services present in both routes."""
    for label, html in (("FR", fr_html), ("EN", en_html)):
        m = re.search(
            r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if not m:
            f.fail(f"{label} page missing JSON-LD schema block")
            continue
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            f.fail(f"{label} page JSON-LD malformed: {e}")
            continue
        graph = data.get("@graph", [])
        types = [n.get("@type") for n in graph]
        # Must have exactly: 1 LocalBusiness, 1 Person, 4 Services.
        if types.count("HealthAndBeautyBusiness") != 1:
            f.fail(f"{label} schema: expected 1 HealthAndBeautyBusiness node, got {types.count('HealthAndBeautyBusiness')}")
        if types.count("Person") != 1:
            f.fail(f"{label} schema: expected 1 Person node, got {types.count('Person')}")
        if types.count("Service") != 4:
            f.fail(f"{label} schema: expected 4 Service nodes, got {types.count('Service')}")


def check_robots_and_sitemap(f: Findings) -> None:
    if not ROBOTS.exists():
        f.fail("robots.txt does not exist")
        return
    robots = ROBOTS.read_text(encoding="utf-8")
    if "Sitemap: https://yogaavecjitendra.fr/sitemap-index.xml" not in robots:
        f.fail("robots.txt missing Sitemap: directive")

    if not SITEMAP_INDEX.exists():
        f.fail("sitemap-index.xml does not exist")
    if not SITEMAP_0.exists():
        f.fail("sitemap-0.xml does not exist")
        return
    sitemap = SITEMAP_0.read_text(encoding="utf-8")
    if "yogaavecjitendra.fr/en/" not in sitemap:
        f.fail("sitemap-0.xml missing EN route")
    if "yoga-jitendra.pages.dev" in sitemap:
        f.fail("sitemap-0.xml contains pages.dev URL leak")


def check_merci_pages(f: Findings) -> None:
    for label, path, needle_lang in (
        ("FR /merci", MERCI_HTML, 'lang="fr"'),
        ("EN /en/thanks", THANKS_HTML, 'lang="en"'),
    ):
        if not path.exists():
            f.fail(f"{label} page does not exist at {path}")
            continue
        html = path.read_text(encoding="utf-8")
        if needle_lang not in html[:200]:
            f.fail(f"{label} page has wrong <html lang> declaration")


def main() -> int:
    for path in (FR_HTML, EN_HTML):
        if not path.exists():
            print(f"FATAL: {path} does not exist. Run `npm run build` first.")
            return 2

    fr_html = FR_HTML.read_text(encoding="utf-8")
    en_html = EN_HTML.read_text(encoding="utf-8")
    f = Findings()

    # FR content on FR page.
    for label, needle in REQUIRED_FR:
        if needle not in fr_html:
            f.fail(f"FR page MISSING [{label}]: '{needle}'")
    # EN content on EN page.
    for label, needle in REQUIRED_EN:
        if needle not in en_html:
            f.fail(f"EN page MISSING [{label}]: '{needle}'")
    # Shared markup on both pages.
    for label, needle in REQUIRED_BOTH:
        if needle not in fr_html:
            f.fail(f"FR page MISSING SHARED [{label}]: '{needle}'")
        if needle not in en_html:
            f.fail(f"EN page MISSING SHARED [{label}]: '{needle}'")
    # Sanskrit + assets on both pages.
    for label, needle in REQUIRED_SANSKRIT + REQUIRED_ASSETS:
        if needle not in fr_html:
            f.fail(f"FR page MISSING [{label}]: '{needle}'")
        if needle not in en_html:
            f.fail(f"EN page MISSING [{label}]: '{needle}'")

    # Banned strings on both pages.
    for label, needle in BANNED_STRINGS:
        if needle in fr_html:
            f.fail(f"FR page LEAKED [{label}]: '{needle}'")
        if needle in en_html:
            f.fail(f"EN page LEAKED [{label}]: '{needle}'")

    # Cross-language leaks.
    for needle in FR_ONLY_MUST_NOT_APPEAR_IN_EN:
        if needle in en_html:
            f.fail(f"CROSS-LANG LEAK: FR-only '{needle}' appears in EN page")
    for needle in EN_ONLY_MUST_NOT_APPEAR_IN_FR:
        if needle in fr_html:
            f.fail(f"CROSS-LANG LEAK: EN-only '{needle}' appears in FR page")

    # SEO primitives + schema + robots + sitemap + conversion pages.
    check_seo_primitives(fr_html, en_html, f)
    check_schema_org(fr_html, en_html, f)
    check_robots_and_sitemap(f)
    check_merci_pages(f)

    if f.errors:
        print(f"FAIL: {len(f.errors)} blocking issue(s):")
        for e in f.errors:
            print(f"  - {e}")
        return 1

    total = (
        len(REQUIRED_FR)
        + len(REQUIRED_EN)
        + 2 * len(REQUIRED_BOTH)
        + 2 * (len(REQUIRED_SANSKRIT) + len(REQUIRED_ASSETS))
        + 2 * len(BANNED_STRINGS)
        + len(FR_ONLY_MUST_NOT_APPEAR_IN_EN)
        + len(EN_ONLY_MUST_NOT_APPEAR_IN_FR)
        # SEO primitives: 4 per route (lang, canonical, 3 hreflang, LCP preload) = 8
        # Schema: 3 per route (Business, Person, 4 Services) = 6
        # robots/sitemap: 5 (robots, sitemap-index, sitemap-0, EN in sitemap, no pages.dev)
        # merci: 2 (FR + EN)
        + 8 + 6 + 5 + 2
    )
    print(f"PASS: yoga_jitendra acceptance gate green — {total} assertions verified across FR + EN + /merci + SEO primitives")
    return 0


if __name__ == "__main__":
    sys.exit(main())
