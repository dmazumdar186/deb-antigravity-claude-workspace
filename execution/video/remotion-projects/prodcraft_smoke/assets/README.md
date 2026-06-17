# Assets

Drop your project assets here before authoring compositions.

## Recommended folder structure

```
assets/
├── audio/
│   ├── voice.mp3      # Main voiceover track (mono or stereo, 44.1 kHz)
│   └── music.mp3      # Background music / bed (keep levels low, -18 dBFS)
└── images/
    ├── hero.jpg        # Primary product or feature shot
    ├── screenshot1.png # Supporting visuals
    └── logo.webp       # Brand logo (transparent preferred)
```

## Notes

- Supported image formats: `.jpg`, `.png`, `.webp`
- Audio files are referenced in compositions via `staticFile("audio/voice.mp3")`
- Images are referenced via `staticFile("images/hero.jpg")`
- Keep originals under 10 MB each; Remotion will not resize at render time
