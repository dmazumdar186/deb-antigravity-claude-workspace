"""Search images by what is in them, with Jev (RoboNuggets use case #14).

description: `index` walks a folder of images (png/jpg/jpeg/webp/gif; videos skipped) and writes
             <dir>/.jev_image_index.json with path, size, dims, mtime and `metadata` text taken
             from (first hit wins): sidecar <name>.txt/.json/.md, a prompts.jsonl /
             prompt_log.jsonl / metadata.json in the image's folder keyed by filename, PNG text
             chunks, EXIF ImageDescription/UserComment, else the filename split into words.
             `--caption` captions metadata-less images (or all with --caption-all) via
             OpenRouter google/gemini-2.5-flash-lite (512 px JPEG data URL). Incremental by
             mtime+size. `search` runs jev_find's two-stage Jev selection over the metadata
             (stage 1: batches <= 25, `choice` + `none` + `noul` abstain, keeps the pick plus
             options >= 35% of its probability; stage 2: final
             `choice` over winners) and prints ranked hits, optional --html contact sheet,
             and a filename-substring baseline count. Directive:
             directives/image_generation/jev_image_search.md
inputs: index --dir path [--recursive] [--caption | --caption-all] [--caption-limit N];
        search --dir path --query "..." [--top 8] [--json] [--html out.html] [--filename-only];
        env OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN).
outputs: <dir>/.jev_image_index.json; ranked hits on stdout (or JSON); optional HTML contact
         sheet; summary "filename matches: N vs Jev matches: M"; ledger row
         .tmp/jev_ledger.jsonl (caller "jev_image_search").
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402
from execution.rag.jev_find import ABSTAIN_BELOW, BATCH_SIZE, _Stats, plan_batches  # noqa: E402

INDEX_NAME = ".jev_image_index.json"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SIDECAR_EXTS = (".txt", ".json", ".md")
LOG_NAMES = ("prompts.jsonl", "prompt_log.jsonl", "metadata.json")
PNG_KEYS = ("prompt", "parameters", "Description", "description", "Comment", "comment", "Title")
TEXT_KEYS = ("prompt", "caption", "description", "text", "metadata", "title")
DESC_CHARS = 300
PREVIEW_CHARS = 160
KEEP_RATIO = 0.35  # stage 1: keep options with p >= 35% of the batch pick
CAPTION_URL = "https://openrouter.ai/api/v1/chat/completions"
CAPTION_MODEL = "google/gemini-2.5-flash-lite"
CAPTION_PROMPT = "Describe this image in one dense sentence: subject, text visible, style, colours."
CAPTION_TIMEOUT_S = 30


# ---- metadata extraction -------------------------------------------------------------------

def safe_path(root: Path, p: Path) -> Path:
    rp = p.resolve()
    if not rp.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes --dir: {p}")
    return rp


def _text_from_obj(obj: Any) -> str:
    if isinstance(obj, str):
        return obj.strip()
    if isinstance(obj, dict):
        for k in TEXT_KEYS:
            if isinstance(obj.get(k), str) and obj[k].strip():
                return obj[k].strip()
        return json.dumps(obj, ensure_ascii=False)[:2000]
    return ""


def _sidecar(img: Path, root: Path) -> str:
    for ext in SIDECAR_EXTS:
        for cand in (img.with_suffix(ext), img.with_name(img.name + ext)):
            if cand.is_file():
                try:
                    safe_path(root, cand)
                    raw = cand.read_text(encoding="utf-8", errors="replace")
                except (OSError, ValueError):
                    continue
                if ext == ".json":
                    try:
                        return _text_from_obj(json.loads(raw))
                    except json.JSONDecodeError:
                        pass
                if raw.strip():
                    return raw.strip()
    return ""


def load_logs(folder: Path, root: Path) -> dict[str, str]:
    """filename -> text from prompts.jsonl / prompt_log.jsonl / metadata.json in a folder."""
    out: dict[str, str] = {}
    for name in LOG_NAMES:
        f = folder / name
        if not f.is_file():
            continue
        try:
            safe_path(root, f)
            raw = f.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue
        rows: list[Any] = []
        if name.endswith(".jsonl"):
            for line in raw.splitlines():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):  # {"file.png": "prompt" | {...}}
                for k, v in data.items():
                    t = _text_from_obj(v)
                    if t:
                        out.setdefault(Path(k).name, t)
                continue
            rows = data if isinstance(data, list) else []
        for r in rows:
            if not isinstance(r, dict):
                continue
            fn = r.get("file") or r.get("filename") or r.get("path") or r.get("image") or ""
            t = _text_from_obj(r)
            if fn and t:
                out.setdefault(Path(str(fn)).name, t)
    return out


def _embedded(im: Any) -> tuple[str, str]:
    for k in PNG_KEYS:
        v = im.info.get(k)
        if isinstance(v, bytes):
            v = v.decode("utf-8", errors="replace")
        if isinstance(v, str) and v.strip():
            return v.strip(), "png_text"
    try:
        exif = im.getexif()
    except Exception:  # noqa: BLE001 - malformed EXIF
        return "", ""
    desc = exif.get(0x010E)  # ImageDescription
    if isinstance(desc, str) and desc.strip():
        return desc.strip(), "exif"
    try:
        uc = exif.get_ifd(0x8769).get(0x9286)  # UserComment
    except Exception:  # noqa: BLE001
        uc = None
    if isinstance(uc, bytes):
        uc = uc[8:].decode("utf-8", errors="ignore") if uc[:8].startswith((b"ASCII", b"UNICODE")) \
            else uc.decode("utf-8", errors="ignore")
    if isinstance(uc, str) and uc.strip("\x00 ").strip():
        return uc.strip("\x00 ").strip(), "exif"
    return "", ""


def filename_words(p: Path) -> str:
    return " ".join(w for w in re.split(r"[\W_]+", p.stem) if w)


def describe(img: Path, root: Path, logs: dict[str, str]) -> dict[str, Any]:
    from PIL import Image
    rec: dict[str, Any] = {"path": img.relative_to(root).as_posix(), "size": img.stat().st_size,
                           "mtime": img.stat().st_mtime, "dims": None, "metadata": "",
                           "source": ""}
    text, src = _sidecar(img, root), "sidecar"
    if not text and img.name in logs:
        text, src = logs[img.name], "log"
    try:
        with Image.open(img) as im:
            rec["dims"] = [im.width, im.height]
            if not text:
                text, src = _embedded(im)
    except Exception as exc:  # noqa: BLE001 - unreadable image: keep filename fallback
        rec["error"] = f"{exc.__class__.__name__}: {exc}"[:200]
    if not text:
        text, src = filename_words(img), "filename"
    rec["metadata"], rec["source"] = text, src
    return rec


def walk_images(root: Path, recursive: bool) -> list[Path]:
    it = root.rglob("*") if recursive else root.glob("*")
    out = []
    for p in it:
        if not p.is_file() or p.suffix.lower() not in IMAGE_EXTS:
            continue
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        try:
            out.append(safe_path(root, p))
        except ValueError as exc:
            print(f"jev_image_search: skipping {p}: {exc}", file=sys.stderr)
    return sorted(out)


# ---- captioning ----------------------------------------------------------------------------

def image_data_url(img: Path, max_px: int = 512) -> str:
    from PIL import Image
    with Image.open(img) as im:
        im = im.convert("RGB")
        im.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def caption(img: Path, *, post: Any = None) -> tuple[str, float, str | None]:
    """Returns (caption, cost_usd, error). Never raises."""
    key = jev_client.api_key()
    if not key:
        return "", 0.0, "no OpenRouter key"
    try:
        if post is None:
            import requests
            post = requests.post
        body = {"model": CAPTION_MODEL, "max_tokens": 80, "usage": {"include": True},
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": CAPTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_data_url(img)}}]}]}
        r = post(CAPTION_URL, json=body, timeout=CAPTION_TIMEOUT_S,
                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        if r.status_code >= 400:
            return "", 0.0, f"HTTP {r.status_code}: {r.text[:200]}"
        data = r.json()
        text = (data["choices"][0]["message"]["content"] or "").strip()
        cost = float((data.get("usage") or {}).get("cost") or 0.0)
        return text, cost, None if text else "empty caption"
    except Exception as exc:  # noqa: BLE001 - fail open
        return "", 0.0, f"{exc.__class__.__name__}: {exc}"[:200]


# ---- index ---------------------------------------------------------------------------------

def load_index(root: Path) -> dict[str, Any]:
    f = root / INDEX_NAME
    if f.is_file():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("images"), dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"version": 1, "images": {}}


def build_index(root: Path, *, recursive: bool = False, do_caption: bool = False,
                caption_all: bool = False, caption_limit: int = 50,
                post: Any = None) -> dict[str, Any]:
    root = root.resolve()
    idx = load_index(root)
    old: dict[str, Any] = idx["images"]
    new: dict[str, Any] = {}
    logs_cache: dict[Path, dict[str, str]] = {}
    stats = {"total": 0, "indexed": 0, "skipped": 0, "captioned": 0, "caption_cost_usd": 0.0,
             "caption_errors": [], "captions": {}}
    for img in walk_images(root, recursive):
        stats["total"] += 1
        rel = img.relative_to(root).as_posix()
        st = img.stat()
        prev = old.get(rel)
        if prev and prev.get("size") == st.st_size and prev.get("mtime") == st.st_mtime \
                and not caption_all:
            new[rel] = prev
            stats["skipped"] += 1
            continue
        if img.parent not in logs_cache:
            logs_cache[img.parent] = load_logs(img.parent, root)
        new[rel] = describe(img, root, logs_cache[img.parent])
        stats["indexed"] += 1
    if do_caption or caption_all:
        for rel, rec in new.items():
            if stats["captioned"] + len(stats["caption_errors"]) >= caption_limit:
                break
            if not caption_all and rec["source"] not in ("filename",):
                continue
            if rec["source"] == "caption" and not caption_all:
                continue
            text, cost, err = caption(root / rel, post=post)
            stats["caption_cost_usd"] += cost
            if err:
                stats["caption_errors"].append(f"{rel}: {err}")
                continue
            rec["metadata"], rec["source"] = text, "caption"
            stats["captioned"] += 1
            stats["captions"][rel] = text
    idx["images"] = new
    idx["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (root / INDEX_NAME).write_text(json.dumps(idx, indent=1, ensure_ascii=False), encoding="utf-8")
    stats["caption_cost_usd"] = round(stats["caption_cost_usd"], 6)
    return stats


# ---- search --------------------------------------------------------------------------------

def filename_matches(images: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    q = query.lower().strip()
    return [im for im in images if q and q in Path(im["path"]).name.lower()]


def _state(query: str) -> dict[str, Any]:
    return {"task": "search a folder of images by what is in them (each option is the image's "
                    "prompt / caption)", "query": query}


def search(query: str, images: list[dict[str, Any]], *, top: int = 8,
           workers: int = 8) -> dict[str, Any]:
    """Two-stage Jev ranking over image metadata. Fails open (empty hits + errors)."""
    t0 = time.perf_counter()
    stats = _Stats()
    batches = plan_batches(len(images))

    def _stage1(idxs: list[int]) -> list[tuple[int, float]]:
        opts = {str(i): images[i]["metadata"][:PREVIEW_CHARS] for i in idxs}
        opts["none"] = "none of these images is about what the query is looking for"
        r = jev_client.decide(_state(query), {
            "best": jev_client.choice("Which image is the one the user is looking for? Judge by "
                                      "what the image shows, not exact words.", opts),
            "any": jev_client.noul("Does any image in this batch match the query?",
                                   "at least one image is clearly about what the query describes",
                                   "no image is about what the query describes")})
        stats.add(r)
        if not r.ok:
            return []
        pick = r.choice("best")
        if pick == "none" or not pick.isdigit() or int(pick) not in idxs:
            return []
        anyp = r.noul("any", 1.0)
        if anyp < ABSTAIN_BELOW:
            return []
        probs = r.probabilities("best") or {pick: r.confidence("best")}
        none_p = probs.get("none", 0.0)
        # unlike jev_find, several images in one batch can match: keep the pick plus every
        # option at least KEEP_RATIO of the pick and above the `none` mass
        floor = max(probs.get(pick, 0.0) * KEEP_RATIO, none_p)
        keep = [(int(k), v * anyp) for k, v in probs.items()
                if k.isdigit() and int(k) in idxs and (k == pick or v >= floor)]
        return keep

    winners: list[tuple[int, float]] = []
    if batches:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            winners = [w for ws in pool.map(_stage1, batches) for w in ws]
    winners.sort(key=lambda w: -w[1])
    winners = winners[:BATCH_SIZE]
    ranked = winners
    if len(winners) > 1:
        opts = {str(i): images[i]["metadata"][:DESC_CHARS] for i, _ in winners}
        r = jev_client.decide(_state(query), {"best": jev_client.choice(
            "Which image best matches what the user is looking for? Judge by meaning.", opts)})
        stats.add(r)
        probs = r.probabilities("best") if r.ok else {}
        if probs:
            ranked = sorted(((i, probs.get(str(i), 0.0)) for i, _ in winners), key=lambda w: -w[1])
    hits = [{**images[i], "probability": round(p, 4)} for i, p in ranked[:max(1, top)]]
    summary = {"images": len(images), "batches": len(batches), "calls": stats.calls,
               "latency_ms": int((time.perf_counter() - t0) * 1000),
               "cost_usd": round(stats.cost, 6), "input_tokens": stats.tokens,
               "errors": stats.errors}
    return {"query": query, "hits": hits, "summary": summary}


def write_html(out: Path, root: Path, query: str, hits: list[dict[str, Any]]) -> None:
    out = out.resolve()
    cards = []
    for h in hits:
        src = os.path.relpath(root / h["path"], out.parent).replace(os.sep, "/")
        p = h.get("probability")
        label = f"p={p:.2f}" if isinstance(p, (int, float)) else "filename match"
        cards.append(
            f'<figure><img src="{html.escape(src, quote=True)}" alt="" loading="lazy">'
            f"<figcaption><b>{html.escape(h['path'])}</b> {label}<br>"
            f"{html.escape(h['metadata'][:200])}</figcaption></figure>")
    doc = ("<!doctype html><meta charset=utf-8><title>Jev image search</title><style>"
           "body{font:14px system-ui;margin:16px}main{display:grid;"
           "grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}"
           "figure{margin:0;border:1px solid #ccc;padding:8px}img{width:100%;height:auto}"
           "</style>" f"<h1>Results for &ldquo;{html.escape(query)}&rdquo;</h1><main>"
           + "".join(cards) + "</main>")
    out.write_text(doc, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Search images by what is in them, with Jev.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("index")
    pi.add_argument("--dir", required=True)
    pi.add_argument("--recursive", action="store_true")
    pi.add_argument("--caption", action="store_true")
    pi.add_argument("--caption-all", action="store_true")
    pi.add_argument("--caption-limit", type=int, default=50)
    ps = sub.add_parser("search")
    ps.add_argument("--dir", required=True)
    ps.add_argument("--query", required=True)
    ps.add_argument("--top", type=int, default=8)
    ps.add_argument("--workers", type=int, default=8)
    ps.add_argument("--json", action="store_true")
    ps.add_argument("--html")
    ps.add_argument("--filename-only", action="store_true")
    a = ap.parse_args(argv)

    root = Path(a.dir).resolve()
    if not root.is_dir():
        print(f"error: --dir is not a directory: {root}", file=sys.stderr)
        return 2
    if a.cmd == "index":
        s = build_index(root, recursive=a.recursive, do_caption=a.caption,
                        caption_all=a.caption_all, caption_limit=max(0, a.caption_limit))
        for rel, cap in s["captions"].items():
            print(f"caption {rel}: {cap}")
        for e in s["caption_errors"]:
            print(f"caption error {e}", file=sys.stderr)
        print(f"index: total={s['total']} indexed={s['indexed']} skipped={s['skipped']} "
              f"captioned={s['captioned']} caption_cost=${s['caption_cost_usd']:.6f} "
              f"-> {root / INDEX_NAME}")
        if s["captioned"] or s["caption_errors"]:
            jev_client.append_ledger({"caller": "jev_image_search", "op": "caption",
                                      "calls": s["captioned"] + len(s["caption_errors"]),
                                      "cost_usd": s["caption_cost_usd"],
                                      "errors": len(s["caption_errors"])})
        return 0

    images = list(load_index(root)["images"].values())
    if not images:
        print("error: empty index; run `index --dir` first", file=sys.stderr)
        return 2
    fn = filename_matches(images, a.query)
    if a.filename_only:
        res = {"query": a.query, "hits": fn[:a.top],
               "summary": {"images": len(images), "filename_matches": len(fn)}}
    else:
        if not jev_client.available():
            print("error: no OpenRouter key (set OPENROUTER_API_KEY)", file=sys.stderr)
            return 2
        res = search(a.query, images, top=a.top, workers=a.workers)
        s = res["summary"]
        s["filename_matches"] = len(fn)
        jev_client.append_ledger({"caller": "jev_image_search", "op": "search",
                                  "calls": s["calls"], "cost_usd": s["cost_usd"],
                                  "input_tokens": s["input_tokens"],
                                  "latency_ms": s["latency_ms"], "errors": len(s["errors"])})
    if a.html:
        write_html(Path(a.html), root, a.query, res["hits"])
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    if not res["hits"]:
        print("no match")
    for n, h in enumerate(res["hits"], 1):
        p = f"p={h['probability']:.2f}" if "probability" in h else "filename"
        print(f"#{n} {h['path']}  {p}  [{h['source']}] {h['metadata'][:120]}")
    s = res["summary"]
    if a.filename_only:
        print(f"summary: images={s['images']} filename matches: {s['filename_matches']}")
    else:
        print(f"summary: images={s['images']} calls={s['calls']} latency={s['latency_ms']}ms "
              f"cost=${s['cost_usd']:.6f} errors={len(s['errors'])} | "
              f"filename matches: {s['filename_matches']} vs Jev matches: {len(res['hits'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
