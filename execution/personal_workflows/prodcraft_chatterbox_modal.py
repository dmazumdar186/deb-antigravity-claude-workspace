"""
description: Modal app deploying ChatterboxTTS (Resemble AI, MIT) as an alternative to F5-TTS. ChatterboxTTS handles long-form conversational/educational content more reliably than F5 — no reference bleeding, no word scrambling at paragraph scale. Same `.synthesize(ref_audio_bytes, ref_text, gen_text)` interface as the F5 wrapper for drop-in swap.

inputs:
    Modal class method:
        synthesize(ref_audio_bytes: bytes, ref_text: str, gen_text: str,
                   remove_silence: bool=False, exaggeration: float=0.5,
                   cfg_weight: float=0.5) -> bytes
            - ref_text is ignored (Chatterbox doesn't need transcript of ref)
            - returns 24kHz mono WAV bytes

    Smoke entrypoint:
        modal run execution/personal_workflows/prodcraft_chatterbox_modal.py \
            --gen-text "..." --out path.wav

outputs:
    Deployed Modal function: prodcraft-chatterbox-tts -> ChatterboxModal.synthesize
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import modal

# ---------------------------------------------------------------------------
# Image: PyTorch + chatterbox-tts + ffmpeg
# ---------------------------------------------------------------------------
CHATTERBOX_IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1", "git")
    .pip_install(
        "torch==2.4.0",
        "torchaudio==2.4.0",
        "soundfile>=0.12",
        "numpy<2.0",
        "huggingface_hub>=0.24",
    )
    .pip_install("chatterbox-tts")
)

HF_CACHE = modal.Volume.from_name("prodcraft-hf-cache", create_if_missing=True)
HF_CACHE_PATH = "/root/.cache/huggingface"

app = modal.App("prodcraft-chatterbox-tts")


@app.cls(
    image=CHATTERBOX_IMAGE,
    gpu="A10G",
    volumes={HF_CACHE_PATH: HF_CACHE},
    timeout=600,
    scaledown_window=300,
)
class ChatterboxModal:
    @modal.enter()
    def load_model(self):
        import os
        os.environ["HF_HOME"] = HF_CACHE_PATH
        from chatterbox.tts import ChatterboxTTS
        self.model = ChatterboxTTS.from_pretrained(device="cuda")
        print("[modal] ChatterboxTTS model loaded", file=sys.stderr)

    @modal.method()
    def synthesize(
        self,
        ref_audio_bytes: bytes,
        ref_text: str,
        gen_text: str,
        remove_silence: bool = False,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
    ) -> bytes:
        import tempfile
        import soundfile as sf
        import torchaudio
        # ref_text unused; Chatterbox derives voice from audio alone.
        _ = ref_text
        _ = remove_silence

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(ref_audio_bytes)
            ref_path = f.name

        try:
            wav = self.model.generate(
                text=gen_text,
                audio_prompt_path=ref_path,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
            )
            # wav is a torch tensor of shape [1, samples] at model.sr (typically 24000)
            sr = self.model.sr
        finally:
            try:
                Path(ref_path).unlink()
            except OSError:
                pass

        # Convert to wav bytes
        buf = io.BytesIO()
        # torchaudio expects [channels, samples]
        torchaudio.save(buf, wav, sr, format="wav", encoding="PCM_S", bits_per_sample=16)
        return buf.getvalue()


@app.local_entrypoint()
def smoke(
    ref_audio: str = ".tmp/prodcraft/voice_sample/voice_sample.wav",
    gen_text: str = "Hey there, this is a smoke test of Chatterbox TTS running on Modal. The prosody should be cleaner for educational long-form content.",
    out: str = ".tmp/prodcraft/chatterbox_smoke.wav",
):
    ref_path = Path(ref_audio).resolve()
    if not ref_path.exists():
        raise SystemExit(f"Reference audio not found: {ref_path}")
    ref_bytes = ref_path.read_bytes()
    print(f"[local] sending ref={ref_path.name} gen={len(gen_text)} chars", file=sys.stderr)
    instance = ChatterboxModal()
    result_bytes = instance.synthesize.remote(
        ref_audio_bytes=ref_bytes,
        ref_text="",  # ignored
        gen_text=gen_text,
    )
    print(f"[local] received {len(result_bytes)} bytes", file=sys.stderr)
    out_path = Path(out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(result_bytes)
    print(f"OK | chatterbox smoke | out={out_path}")
