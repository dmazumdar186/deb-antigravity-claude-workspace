# Ambient audio — license provenance record

Recorded 2026-09-01 by the session that shipped ambient v4 (commit 665d180
and follow-up). Both tracks sourced from Pixabay Music under the **Pixabay
Content License** (https://pixabay.com/service/license-summary/): free for
commercial use including client websites, no attribution required.
Standalone redistribution of the bare files is outside the license, so the
raw mp3 URLs must not be advertised as downloads — embedded site playback
only.

## Track 1 — primary (wired in Base.astro)

- Local file: `public/assets/audio/bansuri-studio.mp3` (processed derivative)
- MD5 (processed, as deployed): `75f7f64e0e96315ef5a23464511701a5` (3,361,324 bytes)
- Source: "bansuri flute" by **PoshPony**, Pixabay id **406082**
- Source page: https://pixabay.com/music/world-bansuri-flute-406082/
- Source CDN file at capture time:
  https://cdn.pixabay.com/download/audio/2025/09/17/audio_0419857538.mp3
  (256 kbps 48 kHz JntStereo, 7,680,768 bytes, duration 4:00)
- Source page metadata captured 2026-09-01 (schema.org JSON-LD): creator
  "PoshPony", uploadDate 2025-09-18, license
  https://pixabay.com/service/license-summary/, isAccessibleForFree true,
  ~51,630 views. NOT tagged AI-generated.
- Processing applied (2026-09-01): PyAV decode → 2 s fade-in + 3 s fade-out
  → peak-normalize -1 dBFS → re-encode 112 kbps 44.1 kHz stereo.

## Track 2 — alternate (deployed, reachable via ?audio=alt)

- Local file: `public/assets/audio/bansuri-raga-alt.mp3` (processed derivative)
- MD5 (processed, as deployed): `0c641e7df05b95e75f202eaee23c7ea9` (6,712,730 bytes)
- Source: "Indian Bansuri Flute Tarana Raga Music" by **boopul**, Pixabay id
  **525950**
- Source page:
  https://pixabay.com/music/meditationspiritual-indian-bansuri-flute-tarana-raga-music-525950/
- Source CDN file at capture time:
  https://cdn.pixabay.com/download/audio/2026/04/28/audio_3d006a0f81.mp3
  (256 kbps 48 kHz JntStereo, 15,341,568 bytes, duration 7:59)
- Source page metadata captured 2026-09-01 (schema.org JSON-LD): creator
  "boopul", uploadDate 2026-04-28, license
  https://pixabay.com/service/license-summary/, isAccessibleForFree true.
  **Tagged "Ai Generated" on Pixabay — disclose if offered to the client.**
- Same processing recipe as track 1.

## Gap / owed action

Full page snapshots (license summary + both track pages as PDF) could not
be captured programmatically on 2026-09-01 — Pixabay's Cloudflare
bot-challenge blocks non-browser fetches, and bypassing bot-detection is
out of policy. **Operator action owed**: open the three URLs above in a
normal browser and print-to-PDF into this directory, ideally from a
logged-in Pixabay account (the account download receipt is the strongest
evidence). Until then, this record plus the in-session JSON-LD captures
above are the provenance trail.
