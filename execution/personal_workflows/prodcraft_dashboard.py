"""
description: Streamlit dashboard for the ProdCraft autopilot approval gate. Lists pending videos, plays each MP4 inline, exposes title/description/tags editors, and Approve/Reject buttons. Backed by execution/personal_workflows/prodcraft_queue.py state.
inputs:
    None (CLI: `streamlit run execution/personal_workflows/prodcraft_dashboard.py`)
outputs:
    Mutates .tmp/prodcraft/queue/<state>/<slug>/{final.mp4,metadata.json}
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
QUEUE_ROOT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "queue"
STATES = ("pending", "approved", "rejected")


def _ensure_dirs() -> None:
    for s in STATES:
        (QUEUE_ROOT / s).mkdir(parents=True, exist_ok=True)


def _items(state: str) -> list[tuple[Path, dict]]:
    out = []
    d = QUEUE_ROOT / state
    if not d.is_dir():
        return out
    for sub in sorted(d.iterdir()):
        if not sub.is_dir():
            continue
        meta_path = sub / "metadata.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        out.append((sub, meta))
    out.sort(key=lambda x: x[1].get("added_at") or "")
    return out


def _save_meta(item_dir: Path, meta: dict) -> None:
    (item_dir / "metadata.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _move(item_dir: Path, new_state: str) -> Path:
    dst = QUEUE_ROOT / new_state / item_dir.name
    shutil.move(str(item_dir), str(dst))
    return dst


def render_item(item_dir: Path, meta: dict, state: str) -> None:
    slug = meta["slug"]
    title = meta.get("title", slug)
    with st.container(border=True):
        st.subheader(f"{title}")
        st.caption(f"slug: `{slug}` · added: {meta.get('added_at', '?')[:19]}")

        col_v, col_meta = st.columns([3, 2])
        with col_v:
            mp4 = item_dir / "final.mp4"
            if mp4.is_file():
                st.video(str(mp4))
            else:
                st.error(f"Missing {mp4}")

        with col_meta:
            new_title = st.text_input("Title", value=meta.get("title", ""), key=f"title_{slug}")
            new_desc = st.text_area(
                "Description", value=meta.get("description", ""), key=f"desc_{slug}", height=140
            )
            new_tags = st.text_input(
                "Tags (comma-separated)",
                value=",".join(meta.get("tags", [])),
                key=f"tags_{slug}",
            )
            new_privacy = st.selectbox(
                "Privacy",
                options=["private", "unlisted", "public"],
                index=["private", "unlisted", "public"].index(meta.get("privacy", "private")),
                key=f"priv_{slug}",
            )
            new_lang = st.selectbox(
                "Language",
                options=["en", "fr"],
                index=["en", "fr"].index(meta.get("language", "en")),
                key=f"lang_{slug}",
            )

            if st.button("Save metadata", key=f"save_{slug}"):
                meta["title"] = new_title
                meta["description"] = new_desc
                meta["tags"] = [t.strip() for t in new_tags.split(",") if t.strip()]
                meta["privacy"] = new_privacy
                meta["language"] = new_lang
                _save_meta(item_dir, meta)
                st.success("Saved")
                st.rerun()

            if state == "pending":
                c_a, c_r = st.columns(2)
                with c_a:
                    if st.button("✓ Approve", key=f"appr_{slug}", type="primary"):
                        meta["title"] = new_title
                        meta["description"] = new_desc
                        meta["tags"] = [t.strip() for t in new_tags.split(",") if t.strip()]
                        meta["privacy"] = new_privacy
                        meta["language"] = new_lang
                        meta["approved_at"] = datetime.now(timezone.utc).isoformat()
                        _save_meta(item_dir, meta)
                        _move(item_dir, "approved")
                        st.success(f"Approved {slug}")
                        st.rerun()
                with c_r:
                    reason = st.text_input("Reject reason", key=f"rsn_{slug}")
                    if st.button("✗ Reject", key=f"rej_{slug}"):
                        meta["rejected_at"] = datetime.now(timezone.utc).isoformat()
                        if reason:
                            meta["rejected_reason"] = reason
                        _save_meta(item_dir, meta)
                        _move(item_dir, "rejected")
                        st.warning(f"Rejected {slug}")
                        st.rerun()
            elif state == "approved":
                if meta.get("uploaded_at"):
                    st.success(
                        f"Uploaded to YouTube: {meta.get('youtube_video_id', '?')} at {meta['uploaded_at'][:19]}"
                    )
                else:
                    st.info("Awaiting Phase 3 upload (run prodcraft_youtube_upload.py)")
                if st.button("Send back to pending", key=f"back_{slug}"):
                    _move(item_dir, "pending")
                    st.rerun()
            else:  # rejected
                st.caption(f"Reason: {meta.get('rejected_reason', '—')}")
                if st.button("Send back to pending", key=f"back_{slug}"):
                    _move(item_dir, "pending")
                    st.rerun()


def main() -> None:
    st.set_page_config(page_title="ProdCraft Autopilot", layout="wide")
    _ensure_dirs()
    st.title("ProdCraft Autopilot — Approval Gate")

    tab_pending, tab_approved, tab_rejected = st.tabs(["Pending", "Approved", "Rejected"])

    for tab, state in ((tab_pending, "pending"), (tab_approved, "approved"), (tab_rejected, "rejected")):
        with tab:
            items = _items(state)
            st.caption(f"{len(items)} item(s)")
            if not items:
                st.info(f"No {state} items.")
                continue
            for item_dir, meta in items:
                render_item(item_dir, meta, state)


if __name__ == "__main__":
    main()
