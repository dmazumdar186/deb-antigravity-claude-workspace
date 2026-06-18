"""
description: Modal app deploying F5-TTS on a GPU container so we are no longer rate-limited by HuggingFace ZeroGPU. Single class with a `synthesize` method that takes ref audio bytes + ref text + gen text and returns rendered wav bytes. Volume-mounts the HF cache so model weights persist across cold starts. Deploy once with `modal deploy execution/personal_workflows/prodcraft_f5_modal.py`; then call from the workspace via `F5TTSModal.synthesize.remote(...)`.

inputs:
    CLI (when invoked locally with `modal run`):
        --ref-audio PATH    reference audio wav (default: .tmp/prodcraft/voice_sample/voice_sample.wav)
        --ref-text "..."    reference transcript (default: read from voice_sample.txt)
        --gen-text "..."    text to synthesize (required for --modal-run)
        --out PATH          where to write the returned wav

    Modal class (when imported & called via .remote()):
        synthesize(ref_audio_bytes: bytes, ref_text: str, gen_text: str, remove_silence: bool=False, speed: float=1.0) -> bytes
            returns rendered wav bytes (24kHz mono PCM s16le)

    Env (for `modal deploy`):
        MODAL_TOKEN_ID, MODAL_TOKEN_SECRET   from .env, configured via `modal token set`

outputs:
    Modal deployed function: prodcraft-f5-tts -> F5TTSModal.synthesize
    Cold-start: ~20s (model load from cached volume); warm call: ~3-8s per paragraph
    Cost at 13 videos/month × ~7 paragraphs × ~5s GPU: ~15 minutes/month, well within Modal $30 free credit.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import modal

# ---------------------------------------------------------------------------
# Image: PyTorch + f5-tts + ffmpeg. The f5-tts pip package pulls torchaudio,
# vocos, and the model loader. We pin to a known-stable version.
# ---------------------------------------------------------------------------
F5_TTS_IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1", "git")
    .pip_install(
        "torch==2.4.0",
        "torchaudio==2.4.0",
        "soundfile>=0.12",
        "numpy<2.0",
        "huggingface_hub>=0.24",
    )
    # f5-tts requires git pulls; install from PyPI for stability.
    .pip_install("f5-tts==0.6.2")
)

# Persistent volume for HuggingFace model cache so cold starts don't re-download
# the ~1GB model every time.
HF_CACHE = modal.Volume.from_name("prodcraft-hf-cache", create_if_missing=True)
HF_CACHE_PATH = "/root/.cache/huggingface"

app = modal.App("prodcraft-f5-tts")


@app.cls(
    image=F5_TTS_IMAGE,
    gpu="A10G",
    volumes={HF_CACHE_PATH: HF_CACHE},
    timeout=600,
    scaledown_window=300,  # keep warm 5 minutes between calls
)
class F5TTSModal:
    """One container per concurrent caller. Model loaded once per container."""

    @modal.enter()
    def load_model(self):
        """Load F5-TTS on container start. Runs once per cold-start."""
        import os
        os.environ["HF_HOME"] = HF_CACHE_PATH
        from f5_tts.api import F5TTS
        # f5-tts 0.6.2 default constructor loads the default F5-TTS model.
        # Model auto-downloads to volume on first call; subsequent calls hit cache.
        self.tts = F5TTS()
        print("[modal] F5-TTS model loaded", file=sys.stderr)

    @modal.method()
    def synthesize(
        self,
        ref_audio_bytes: bytes,
        ref_text: str,
        gen_text: str,
        remove_silence: bool = False,
        speed: float = 1.0,
    ) -> bytes:
        """Run F5-TTS inference. Returns wav bytes (24kHz mono PCM s16le)."""
        import tempfile
        import soundfile as sf

        # Write ref audio to a temp file (F5-TTS API accepts a filepath).
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(ref_audio_bytes)
            ref_path = f.name

        try:
            wav, sr, _spec = self.tts.infer(
                ref_file=ref_path,
                ref_text=ref_text,
                gen_text=gen_text,
                remove_silence=remove_silence,
                speed=speed,
                file_wave=None,  # don't write to disk; we return bytes
            )
        finally:
            try:
                Path(ref_path).unlink()
            except OSError:
                # Best-effort cleanup of the temp ref file; container is ephemeral.
                pass

        # Encode to wav bytes.
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV", subtype="PCM_16")
        return buf.getvalue()


# ---------------------------------------------------------------------------
# Local entrypoint: `modal run execution/personal_workflows/prodcraft_f5_modal.py`
# Smoke-tests the deployment end-to-end against the workspace voice_sample.
# ---------------------------------------------------------------------------
@app.local_entrypoint()
def smoke(
    ref_audio: str = ".tmp/prodcraft/voice_sample/voice_sample.wav",
    ref_text: str | None = None,
    gen_text: str = "Hello everyone, this is a smoke test of F5 TTS running on Modal.",
    out: str = ".tmp/prodcraft/modal_smoke.wav",
    speed: float = 1.0,
):
    """Run one synthesis through the Modal endpoint and write the result locally."""
    ref_path = Path(ref_audio).resolve()
    if not ref_path.exists():
        raise SystemExit(f"Reference audio not found: {ref_path}")

    if ref_text is None:
        txt_path = ref_path.with_name("voice_sample.txt")
        if not txt_path.exists():
            raise SystemExit(f"Reference transcript not found: {txt_path}")
        ref_text = txt_path.read_text(encoding="utf-8").strip()

    ref_bytes = ref_path.read_bytes()
    print(f"[local] sending ref={ref_path.name} ({len(ref_bytes)} bytes) gen={len(gen_text)} chars", file=sys.stderr)

    instance = F5TTSModal()
    result_bytes = instance.synthesize.remote(
        ref_audio_bytes=ref_bytes,
        ref_text=ref_text,
        gen_text=gen_text,
        speed=speed,
    )
    print(f"[local] received {len(result_bytes)} bytes", file=sys.stderr)

    out_path = Path(out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(result_bytes)
    print(f"OK | modal f5-tts smoke | out={out_path}")
