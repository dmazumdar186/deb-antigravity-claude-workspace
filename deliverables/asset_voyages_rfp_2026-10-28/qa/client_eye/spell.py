"""B5 spell check for the client-eye gate.

Input: words.json (visible strings per page, with the page language) and allowlist_spell.tsv
(word<TAB>lang<TAB>reason; every allowlisted word needs a reason). Uses pyspellchecker's fr and en dictionaries.
Text inside « » on an English page is French (quoted UI labels). Prints JSON: {"unknown": [...], "allowlist_errors": [...]}.
"""
import json
import re
import sys
import unicodedata

from spellchecker import SpellChecker

words_file, allow_file = sys.argv[1], sys.argv[2]
pages = json.load(open(words_file, encoding="utf-8"))

allow = {"fr": set(), "en": set(), "*": set()}
allow_errors = []
for n, line in enumerate(open(allow_file, encoding="utf-8"), 1):
    line = line.rstrip("\n")
    if not line or line.startswith("#"):
        continue
    parts = line.split("\t")
    if len(parts) < 3 or not parts[2].strip():
        allow_errors.append(f"line {n}: no reason given: {line!r}")
        continue
    allow.setdefault(parts[1], set()).add(parts[0].lower())

sp = {"fr": SpellChecker(language="fr"), "en": SpellChecker(language="en")}
WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ]+(?:[-][A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*")
# e-mails may be split over two lines (« chloe.petit @example .com » once line boxes are joined), so spaces are allowed
URLISH = re.compile(r"https?://\S+|www\.\S+|[\w.+-]+\s?@\s?[\w-]+(?:\s?\.\s?[\w-]+)+|\b[\w-]+\.(?:com|org|net|fyi|dev|fr|php|json|js|csv|zip|mp4)\b|\b[A-Z]{2,}-\d+\S*|DEMO-GME-\S+")


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def known(word, lang):
    w = word.lower()
    if w in allow.get(lang, set()) or w in allow["*"]:
        return True
    d = sp[lang]
    if w in d:
        return True
    # French elision: l’équipe, d’accès, qu’il, n’est, j’accepte
    return False


def split_tokens(text):
    text = URLISH.sub(" ", text)
    text = re.sub(r"\b(?:l|d|j|m|n|s|t|c|qu|jusqu|lorsqu|puisqu)['’]", " ", text, flags=re.I)
    text = text.replace("’", "'")
    out = []
    for m in WORD.finditer(text):
        w = m.group(0)
        if len(w) < 3:
            continue
        if w.isupper() and len(w) <= 6:  # acronyms: GM&E, CSV, RGPD, ASSET (checked by the allowlist when longer)
            continue
        out.append(w)
    return out


unknown = {}
for p in pages:
    lang = p["lang"]
    for text in p["texts"] + p.get("attrs", []):
        segments = []
        if lang == "en":
            # French quoted labels inside an English page
            for q in re.findall(r"«([^»]*)»", text):
                segments.append((q, "fr"))
            segments.append((re.sub(r"«[^»]*»", " ", text), "en"))
        else:
            segments.append((text, "fr"))
        for seg, l in segments:
            for w in split_tokens(seg):
                parts = w.split("-")
                bad = [x for x in parts if len(x) >= 3 and not known(x, l)] if not known(w, l) else []
                if not bad:
                    continue
                key = (w.lower(), l)
                e = unknown.setdefault(key, {"word": w, "lang": l, "count": 0, "option": p["option"], "page": p["page"], "role": p["role"], "width": p["width"], "context": seg.strip()[:120]})
                e["count"] += 1

print(json.dumps({"unknown": sorted(unknown.values(), key=lambda e: (e["option"], e["word"].lower())), "allowlist_errors": allow_errors}, ensure_ascii=False))
