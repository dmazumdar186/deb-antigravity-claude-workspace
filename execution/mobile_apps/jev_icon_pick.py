"""Pick an app icon from what the user types, with Jev (TypeSafe decision model via OpenRouter).

description: RoboNuggets use case 17. Given free text ("drink more water", "rough day at
             work") and an icon set (name -> one-line description), Jev picks the icon in
             one ~200 ms choice call. Sets above 40 options are split into batches and the
             batch winners go to a second, final call (same shape as execution/rag/jev_find.py).
             Below --min-confidence the answer is `none`. A keyword-overlap regex baseline is
             included so `bench --compare-regex` shows the gap. Fails open: errors return
             icon=None with `error` set. Directive: directives/mobile_apps/jev_icon_pick.md
inputs: `pick "<text>"` [--mode habit|mood|generic] [--icons app_icons.json] [--top-k 3]
        [--min-confidence 0.4] [--json]; `bench` [--bench path] [--compare-regex];
        env OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN).
outputs: pick -> {icon, confidence, alternatives:[{icon, probability}], cost, latency_ms, error};
         bench -> accuracy, top-3, mean latency, total cost, mismatches (stdout, --json for
         machine output); ledger row in .tmp/jev_ledger.jsonl (caller "jev_icon_pick").
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402

BATCH_MAX = 40  # options per Jev call, `none` included
NONE = "none"
NONE_DESC = "no icon fits; the text is unrelated to every listed icon"
DEFAULT_BENCH = _ROOT / "execution" / "infrastructure" / "jev_specs" / "icon_bench.json"

DEFAULT_ICONS: dict[str, str] = {
    # health / habits
    "droplet": "water, hydration, drink more water, drinking",
    "glass-water": "glass of water, drinking water, hydrate",
    "coffee": "coffee, tea, caffeine, morning drink, cafe",
    "wine": "wine, alcohol, drinks, bar",
    "cigarette-off": "quit smoking, no cigarettes, stop vaping",
    "dumbbell": "exercise, gym, strength training, lifting weights, workout",
    "footprints": "walking, steps, step count, hike",
    "bike": "cycling, bike ride, bicycle",
    "activity": "running, jogging, cardio, heart rate, fitness activity",
    "heart-pulse": "health, heart, blood pressure, vitals",
    "pill": "medicine, pills, vitamins, take medication, supplements",
    "apple": "healthy eating, fruit, diet, nutrition, eat vegetables",
    "salad": "salad, vegetables, eat greens, healthy meal",
    "utensils": "meals, eating, food, cooking dinner, lunch",
    "chef-hat": "cooking, cook at home, recipes, baking",
    "moon": "sleep, bedtime, night, go to bed early, rest",
    "bed": "sleep, nap, bed, make the bed",
    "alarm-clock": "wake up early, alarm, morning routine",
    "sun": "sunshine, outdoors, morning, get daylight, weather sunny",
    "brain": "meditation, mindfulness, mental health, focus, think",
    "flower": "meditation, calm, yoga, relaxation, gratitude",
    "smile-plus": "gratitude, kindness, be nice to someone",
    "toothbrush": "brush teeth, floss, dental hygiene",
    "shower-head": "shower, bath, hygiene, cold shower",
    "scale": "weight, weigh yourself, lose weight",
    # learning / work
    "book-open": "reading, read a book, study, learn",
    "graduation-cap": "school, course, studying, exam, education",
    "languages": "learn a language, Spanish, French, vocabulary, Duolingo",
    "pen-line": "writing, journal, diary, notes, write",
    "notebook": "journal, notebook, planning, notes",
    "code": "coding, programming, software, practice code",
    "laptop": "computer work, laptop, office work, emails",
    "briefcase": "work, job, career, business, meeting",
    "calendar": "schedule, plan the week, appointments, calendar",
    "check-square": "to-do, tasks, checklist, get things done",
    "target": "goals, focus, aim, objective",
    "timer": "pomodoro, time tracking, focus session, deadline",
    "music": "music, practice instrument, piano, guitar, listen to songs",
    "palette": "art, painting, drawing, creativity",
    "camera": "photography, take photos, camera",
    "mic": "podcast, singing, voice, record audio",
    # money / home
    "piggy-bank": "save money, savings, budget",
    "wallet": "spending, money, wallet, expenses",
    "credit-card": "credit card, payments, bills",
    "shopping-cart": "groceries, shopping, buy",
    "home": "home, house, chores at home",
    "sparkles": "clean, tidy up, declutter, cleaning",
    "trash-2": "take out the trash, garbage, throw away",
    "shirt": "laundry, clothes, outfit",
    "sprout": "plants, water the plants, gardening, growth",
    "dog": "dog, walk the dog, pet, puppy",
    "cat": "cat, feed the cat, pet",
    "baby": "baby, children, kids, parenting",
    # social / leisure
    "phone": "call someone, phone call, call mom",
    "phone-off": "less screen time, no phone, digital detox, social media break",
    "message-circle": "text, message friends, chat, reply",
    "users": "friends, family, socialize, meet people",
    "heart": "love, partner, date night, relationship, romance",
    "gift": "gift, birthday, present, celebration",
    "gamepad-2": "video games, gaming, play",
    "tv": "TV, watch a show, movies, Netflix",
    "plane": "travel, flight, trip, vacation",
    "car": "drive, car, commute",
    "tent": "camping, outdoors, nature trip",
    "mountain": "hiking, climbing, mountains, adventure",
    "waves": "swimming, beach, ocean, surf",
    "trophy": "achievement, win, competition, milestone",
    "star": "favorite, highlight, special, rating",
    "flame": "streak, motivation, burn calories, energy",
    "church": "prayer, faith, church, spirituality",
    # mood
    "smile": "happy mood, good day, joyful, content, felt great",
    "laugh": "very happy, ecstatic, fun, laughing, amazing day",
    "meh": "neutral mood, okay day, so-so, nothing special, bored",
    "frown": "sad mood, bad day, down, disappointed, unhappy",
    "angry": "angry, frustrated, annoyed, irritated mood",
    "annoyed": "stressed, anxious, overwhelmed, tense mood",
    "cloud-rain": "gloomy, depressed, rainy weather, melancholy",
    "zap": "energized, productive, excited, high energy",
    "battery-low": "tired, exhausted, drained, low energy, burnt out",
    "thermometer": "sick, fever, ill, unwell, cold",
}

MODE_INSTRUCTIONS: dict[str, str] = {
    "habit": ("The user is naming a habit to track in a habit-tracker app. Which icon best "
              "represents that habit? Judge by meaning, not by shared words."),
    "mood": ("The user is describing their day or how they feel in a mood-journal app. Which "
             "icon best represents their overall mood? Judge by the feeling, not by activities mentioned."),
    "generic": "Which icon best represents what the user typed? Judge by meaning, not by shared words.",
}
MOOD_ICONS = ("smile", "laugh", "meh", "frown", "angry", "annoyed", "cloud-rain", "zap",
              "battery-low", "thermometer")


def plan_batches(names: list[str], size: int = BATCH_MAX - 1) -> list[list[str]]:
    """Split icon names into batches of `size` (one slot per call is kept for `none`)."""
    size = max(1, min(size, BATCH_MAX - 1))
    return [names[i:i + size] for i in range(0, len(names), size)]


def _question(mode: str, icons: dict[str, str], names: list[str]) -> dict[str, Any]:
    opts = {n: icons[n][:200] for n in names}
    opts[NONE] = NONE_DESC
    return {"icon": jev_client.choice(MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["generic"]), opts)}


def _state(text: str, mode: str) -> dict[str, Any]:
    return {"app": f"{mode} app icon picker", "user_typed": text}


def pick_icon(text: str, icons: dict[str, str] | None = None, *, top_k: int = 3,
              min_confidence: float = 0.4, mode: str = "generic") -> dict[str, Any]:
    """Return {icon, confidence, alternatives, cost, latency_ms, error}. Never raises."""
    t0 = time.perf_counter()
    icons = {k: v for k, v in (icons or DEFAULT_ICONS).items() if k != NONE}
    out: dict[str, Any] = {"icon": None, "confidence": 0.0, "alternatives": [], "cost": 0.0,
                           "latency_ms": 0, "error": None, "calls": 0}
    text = (text or "").strip()
    if not text or not icons:
        out["error"] = "empty text" if not text else "empty icon set"
        return out
    state = _state(text, mode)
    errors: list[str] = []
    lock = threading.Lock()  # batches run in a thread pool; counters are shared

    def _ask(names: list[str]) -> dict[str, float]:
        r = jev_client.decide(state, _question(mode, icons, names))
        with lock:
            out["cost"] += r.cost_usd
            out["calls"] += 1
            if not r.ok:
                errors.append(r.error or "no answer")
        if not r.ok:
            return {}
        probs = r.probabilities("icon")
        if not probs and r.choice("icon"):
            probs = {r.choice("icon"): r.confidence("icon")}
        return probs

    names = list(icons)
    batches = plan_batches(names)
    if len(batches) == 1:
        probs = _ask(names)
    else:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(8, len(batches))) as pool:
            stage1 = list(pool.map(_ask, batches))
        finalists: list[tuple[str, float]] = []
        for p in stage1:
            real = sorted(((k, v) for k, v in p.items() if k in icons), key=lambda kv: -kv[1])
            finalists.extend(real[:max(1, top_k)])
        finalists = sorted(finalists, key=lambda kv: -kv[1])[:BATCH_MAX - 1]
        probs = _ask([k for k, _ in finalists]) if finalists else {}
    out["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    out["cost"] = round(out["cost"], 6)
    if errors and not probs:
        out["error"] = "; ".join(e[:200] for e in errors)
        return out
    ranked = sorted(((k, v) for k, v in probs.items() if k in icons), key=lambda kv: -kv[1])
    out["alternatives"] = [{"icon": k, "probability": round(v, 4)} for k, v in ranked[:max(1, top_k)]]
    best, conf = (ranked[0] if ranked else (NONE, probs.get(NONE, 0.0)))
    if best == NONE or conf < min_confidence:
        out["icon"], out["confidence"] = NONE, round(probs.get(NONE, 1.0 - conf), 4)
    else:
        out["icon"], out["confidence"] = best, round(conf, 4)
    return out


# ---- regex baseline ------------------------------------------------------------------------

_TOKEN = re.compile(r"[a-z]+")
_STOP = {"a", "an", "the", "to", "of", "and", "or", "my", "i", "in", "on", "for", "at", "it",
         "was", "is", "more", "less", "some", "with", "do", "go", "get", "today", "day", "felt"}


def _tokens(s: str) -> set[str]:
    return {t for t in _TOKEN.findall(s.lower()) if t not in _STOP and len(t) > 1}


def regex_pick(text: str, icons: dict[str, str] | None = None, top_k: int = 3) -> list[str]:
    """Keyword-overlap baseline: rank icons by shared tokens with name+description. [] -> none."""
    icons = icons or DEFAULT_ICONS
    q = _tokens(text)
    scored = []
    for name, desc in icons.items():
        if name == NONE:
            continue
        hits = len(q & _tokens(name.replace("-", " ") + " " + desc))
        if hits:
            scored.append((hits, name))
    scored.sort(key=lambda s: (-s[0], list(icons).index(s[1])))
    return [n for _, n in scored[:top_k]]


# ---- bench -----------------------------------------------------------------------------------

def score_bench(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """rows: {text, expected (str or list), predicted, top (list), latency_ms, cost}."""
    n = len(rows) or 1
    def _exp(r: dict[str, Any]) -> set[str]:
        e = r["expected"]
        return set(e if isinstance(e, list) else [e])
    hit = sum(1 for r in rows if r["predicted"] in _exp(r))
    top = sum(1 for r in rows if r["predicted"] in _exp(r) or _exp(r) & set(r.get("top") or []))
    return {"n": len(rows), "accuracy": round(hit / n, 3), "top3": round(top / n, 3),
            "mean_latency_ms": round(sum(r.get("latency_ms", 0) for r in rows) / n, 1),
            "cost_usd": round(sum(r.get("cost", 0.0) for r in rows), 6),
            "mismatches": [{"text": r["text"], "expected": r["expected"], "got": r["predicted"]}
                           for r in rows if r["predicted"] not in _exp(r)]}


def run_bench(path: Path, *, compare_regex: bool = False, min_confidence: float = 0.4) -> dict[str, Any]:
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    rows, rx = [], []
    for c in cases:
        r = pick_icon(c["text"], top_k=3, min_confidence=min_confidence, mode=c.get("mode", "habit"))
        rows.append({"text": c["text"], "expected": c["expected"], "predicted": r["icon"],
                     "top": [a["icon"] for a in r["alternatives"]], "latency_ms": r["latency_ms"],
                     "cost": r["cost"], "error": r["error"]})
        if compare_regex:
            t = time.perf_counter()
            top = regex_pick(c["text"])
            rx.append({"text": c["text"], "expected": c["expected"], "predicted": top[0] if top else NONE,
                       "top": top, "latency_ms": (time.perf_counter() - t) * 1000, "cost": 0.0})
    out = {"jev": score_bench(rows), "errors": [r["error"] for r in rows if r["error"]]}
    if compare_regex:
        out["regex"] = score_bench(rx)
    jev_client.append_ledger({"caller": "jev_icon_pick", "op": "bench", "items": len(rows),
                              "cost_usd": out["jev"]["cost_usd"],
                              "latency_ms": out["jev"]["mean_latency_ms"]})
    return out


def _load_icons(path: str | None) -> dict[str, str]:
    if not path:
        return DEFAULT_ICONS
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
        raise ValueError("--icons must be a JSON object of name -> description")
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Jev icon picker (use case 17)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    p.add_argument("text")
    p.add_argument("--mode", choices=sorted(MODE_INSTRUCTIONS), default="habit")
    p.add_argument("--icons")
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--min-confidence", type=float, default=0.4)
    p.add_argument("--json", action="store_true")
    b = sub.add_parser("bench")
    b.add_argument("--bench", default=str(DEFAULT_BENCH))
    b.add_argument("--compare-regex", action="store_true")
    b.add_argument("--min-confidence", type=float, default=0.4)
    b.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not jev_client.available():
        print("no OpenRouter key (set OPENROUTER_API_KEY)", file=sys.stderr)
        return 2
    if a.cmd == "pick":
        try:
            icons = _load_icons(a.icons)
        except (OSError, ValueError) as exc:
            print(f"bad --icons: {exc}", file=sys.stderr)
            return 2
        if a.mode == "mood" and not a.icons:
            icons = {k: DEFAULT_ICONS[k] for k in MOOD_ICONS}
        r = pick_icon(a.text, icons, top_k=a.top_k, min_confidence=a.min_confidence, mode=a.mode)
        jev_client.append_ledger({"caller": "jev_icon_pick", "op": "pick", "items": 1,
                                  "cost_usd": r["cost"], "latency_ms": r["latency_ms"]})
        if a.json:
            print(json.dumps(r, indent=2))
        else:
            alts = ", ".join(f"{x['icon']} {x['probability']:.2f}" for x in r["alternatives"])
            print(f"{r['icon']} ({r['confidence']:.2f})  top: {alts}  "
                  f"{r['latency_ms']} ms  ${r['cost']:.6f}" + (f"  error: {r['error']}" if r["error"] else ""))
        return 0 if not r["error"] else 1
    res = run_bench(Path(a.bench), compare_regex=a.compare_regex, min_confidence=a.min_confidence)
    if a.json:
        print(json.dumps(res, indent=2))
        return 0
    for k in ("jev", "regex"):
        if k in res:
            s = res[k]
            print(f"{k:5} n={s['n']} acc={s['accuracy']:.0%} top3={s['top3']:.0%} "
                  f"lat={s['mean_latency_ms']:.0f}ms cost=${s['cost_usd']:.6f}")
            for m in s["mismatches"]:
                print(f"   x {m['text']!r}: expected {m['expected']} got {m['got']}")
    if res["errors"]:
        print(f"errors: {res['errors'][:3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
