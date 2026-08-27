// Service icon library — simplified brand-recognizable glyphs.
// Each icon is a 48x48 viewBox SVG rendered inside a 64px circle on the card.
// Not pixel-perfect logos — enough to communicate the service at a glance.

window.ICONS = {
  slack: {
    color: "#4A154B",
    bg: "#F4F0F5",
    svg: `<g transform="translate(6 6)">
      <rect x="14" y="0" width="7" height="21" rx="3.5" fill="#E01E5A"/>
      <rect x="14" y="21" width="7" height="15" rx="3.5" fill="#E01E5A"/>
      <rect x="0" y="14" width="21" height="7" rx="3.5" fill="#36C5F0"/>
      <rect x="21" y="14" width="15" height="7" rx="3.5" fill="#36C5F0"/>
      <rect x="14" y="14" width="7" height="7" rx="3.5" fill="#ECB22E"/>
      <rect x="14" y="0" width="7" height="7" rx="3.5" fill="#E01E5A"/>
      <rect x="0" y="14" width="7" height="7" rx="3.5" fill="#36C5F0"/>
      <rect x="14" y="29" width="7" height="7" rx="3.5" fill="#2EB67D"/>
    </g>`
  },
  clickup: {
    color: "#7B68EE",
    bg: "#EEE9FF",
    svg: `<path d="M8 32 L 24 16 L 40 32 L 34 36 L 24 26 L 14 36 Z" fill="#7B68EE"/>
          <path d="M8 40 L 24 26 L 40 40 L 34 44 L 24 34 L 14 44 Z" fill="#7B68EE" opacity="0.5"/>`
  },
  googleCalendar: {
    color: "#4285F4",
    bg: "#E8F0FE",
    svg: `<rect x="6" y="8" width="36" height="34" rx="4" fill="#fff" stroke="#4285F4" stroke-width="2"/>
          <rect x="6" y="8" width="36" height="9" rx="4" fill="#4285F4"/>
          <text x="24" y="35" text-anchor="middle" font-family="Arial,sans-serif" font-size="16" font-weight="700" fill="#4285F4">31</text>`
  },
  googleSheets: {
    color: "#0F9D58",
    bg: "#E6F4EA",
    svg: `<rect x="10" y="6" width="28" height="36" rx="2" fill="#fff" stroke="#0F9D58" stroke-width="2"/>
          <path d="M15 18 H 33 M15 26 H 33 M15 34 H 33 M21 14 V 40 M27 14 V 40" stroke="#0F9D58" stroke-width="1.5"/>`
  },
  googleDrive: {
    color: "#1FA463",
    bg: "#E6F4EA",
    svg: `<g transform="translate(4 6)">
      <path d="M14 0 L 26 0 L 40 24 L 34 36 L 20 12 Z" fill="#FFC107"/>
      <path d="M14 0 L 20 12 L 6 36 L 0 24 Z" fill="#1FA463"/>
      <path d="M6 36 L 34 36 L 28 46 L 12 46 Z" fill="#4285F4"/>
    </g>`
  },
  gemini: {
    color: "#4285F4",
    bg: "#E8F0FE",
    svg: `<path d="M24 4 L 27 18 L 44 24 L 27 30 L 24 44 L 21 30 L 4 24 L 21 18 Z" fill="url(#gemGrad)"/>
          <defs><linearGradient id="gemGrad" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stop-color="#4285F4"/><stop offset="1" stop-color="#A142F4"/>
          </linearGradient></defs>`
  },
  openai: {
    color: "#10A37F",
    bg: "#E6F5F0",
    svg: `<g transform="translate(24 24)" fill="#10A37F">
      <g id="o-blade"><path d="M0 -18 L 6 -8 L 0 -14 L -6 -8 Z"/></g>
      <use href="#o-blade" transform="rotate(60)"/>
      <use href="#o-blade" transform="rotate(120)"/>
      <use href="#o-blade" transform="rotate(180)"/>
      <use href="#o-blade" transform="rotate(240)"/>
      <use href="#o-blade" transform="rotate(300)"/>
    </g>`
  },
  anthropic: {
    color: "#D97757",
    bg: "#FDEDE6",
    svg: `<path d="M18 6 L 30 6 L 42 42 L 34 42 L 31 33 L 17 33 L 14 42 L 6 42 Z M 20 27 L 28 27 L 24 15 Z" fill="#D97757"/>`
  },
  claude: {
    color: "#D97757",
    bg: "#FDEDE6",
    svg: `<path d="M18 6 L 30 6 L 42 42 L 34 42 L 31 33 L 17 33 L 14 42 L 6 42 Z M 20 27 L 28 27 L 24 15 Z" fill="#D97757"/>`
  },
  cloudflare: {
    color: "#F38020",
    bg: "#FEF0E5",
    svg: `<path d="M35 30 Q 42 30 42 24 Q 42 18 34 17 Q 32 8 22 8 Q 12 8 10 18 Q 4 19 4 25 Q 4 30 10 30 Z" fill="#F38020"/>
          <path d="M4 30 L 42 30 L 40 34 L 6 34 Z" fill="#FBAD41"/>`
  },
  github: {
    color: "#1F2328",
    bg: "#F0F0F0",
    svg: `<path d="M24 4 C 13 4 4 13 4 24 C 4 33 10 40 18 42 L 18 38 C 12 39 11 35 11 35 C 10 33 9 33 9 33 C 7 32 9 32 9 32 C 11 32 12 34 12 34 C 14 37 17 36 18 36 C 18 34 19 33 20 33 C 15 32 10 30 10 22 C 10 20 11 18 12 17 C 12 16 11 14 12 12 C 12 12 14 12 18 15 C 20 14 22 14 24 14 C 26 14 28 14 30 15 C 34 12 36 12 36 12 C 37 14 36 16 36 17 C 37 18 38 20 38 22 C 38 30 33 32 28 33 C 29 34 30 35 30 37 L 30 42 C 38 40 44 33 44 24 C 44 13 35 4 24 4 Z" fill="#1F2328"/>`
  },
  instagram: {
    color: "#E4405F",
    bg: "#FEE7EC",
    svg: `<rect x="6" y="6" width="36" height="36" rx="10" fill="url(#igGrad)"/>
          <circle cx="24" cy="24" r="8" fill="none" stroke="#fff" stroke-width="2.5"/>
          <circle cx="35" cy="13" r="2" fill="#fff"/>
          <defs><linearGradient id="igGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#F58529"/><stop offset="0.5" stop-color="#DD2A7B"/><stop offset="1" stop-color="#8134AF"/>
          </linearGradient></defs>`
  },
  youtube: {
    color: "#FF0000",
    bg: "#FEE5E5",
    svg: `<rect x="4" y="12" width="40" height="24" rx="6" fill="#FF0000"/>
          <path d="M20 18 L 32 24 L 20 30 Z" fill="#fff"/>`
  },
  instantly: {
    color: "#635BFF",
    bg: "#EEEDFF",
    svg: `<path d="M6 12 L 42 12 L 42 36 L 6 36 Z M 6 12 L 24 26 L 42 12" fill="none" stroke="#635BFF" stroke-width="2.5" stroke-linejoin="round"/>
          <circle cx="36" cy="32" r="5" fill="#635BFF"/>`
  },
  ghl: {
    color: "#4B60D8",
    bg: "#EAECFB",
    svg: `<path d="M8 8 L 40 8 L 40 22 L 26 22 L 26 40 L 8 40 Z" fill="#4B60D8"/>
          <text x="17" y="17" text-anchor="middle" font-family="Arial,sans-serif" font-size="11" font-weight="700" fill="#fff">GHL</text>`
  },
  webhooks: {
    color: "#C73A63",
    bg: "#FBE7EE",
    svg: `<path d="M24 6 L 30 20 L 22 18 L 18 32 L 12 30 L 18 14 L 12 16 Z" fill="#C73A63"/>
          <circle cx="30" cy="34" r="5" fill="#C73A63"/>
          <circle cx="14" cy="36" r="5" fill="#C73A63" opacity="0.6"/>`
  },
  router: {
    color: "#22C55E",
    bg: "#DFF7E4",
    svg: `<path d="M24 4 L 44 24 L 24 44 L 4 24 Z" fill="#22C55E"/>
          <path d="M12 24 L 36 24 M 30 18 L 36 24 L 30 30" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>`
  },
  python: {
    color: "#3776AB",
    bg: "#E5EEF6",
    svg: `<path d="M24 4 C 16 4 14 7 14 12 L 14 18 L 24 18 L 24 20 L 8 20 C 4 20 2 24 2 30 C 2 36 4 38 8 38 L 12 38 L 12 32 C 12 28 14 26 18 26 L 30 26 C 33 26 34 24 34 20 L 34 12 C 34 7 32 4 24 4 Z M 19 8 A 2 2 0 1 1 19 12 A 2 2 0 1 1 19 8 Z" fill="#3776AB"/>
          <path d="M24 44 C 32 44 34 41 34 36 L 34 30 L 24 30 L 24 28 L 40 28 C 44 28 46 24 46 18 C 46 12 44 10 40 10 L 36 10 L 36 16 C 36 20 34 22 30 22 L 18 22 C 15 22 14 24 14 28 L 14 36 C 14 41 16 44 24 44 Z M 29 40 A 2 2 0 1 1 29 36 A 2 2 0 1 1 29 40 Z" fill="#FFD43B"/>`
  },
  modal: {
    color: "#7FEE64",
    bg: "#EDFCE7",
    svg: `<rect x="6" y="6" width="36" height="36" rx="6" fill="#1F2328"/>
          <path d="M14 34 L 14 14 L 20 14 L 24 22 L 28 14 L 34 14 L 34 34 L 28 34 L 28 22 L 24 30 L 20 22 L 20 34 Z" fill="#7FEE64"/>`
  },
  huggingface: {
    color: "#FF9D00",
    bg: "#FFF3E0",
    svg: `<circle cx="24" cy="24" r="18" fill="#FFD21E"/>
          <circle cx="17" cy="22" r="2" fill="#000"/>
          <circle cx="31" cy="22" r="2" fill="#000"/>
          <path d="M15 30 Q 24 36 33 30" stroke="#000" stroke-width="2" fill="none" stroke-linecap="round"/>
          <ellipse cx="12" cy="30" rx="3" ry="2" fill="#FF6E6E" opacity="0.7"/>
          <ellipse cx="36" cy="30" rx="3" ry="2" fill="#FF6E6E" opacity="0.7"/>`
  },
  streamlit: {
    color: "#FF4B4B",
    bg: "#FEE5E5",
    svg: `<path d="M4 14 L 44 14 L 24 30 Z" fill="#FF4B4B"/>
          <path d="M8 24 L 40 24 L 24 34 Z" fill="#FF9C9C"/>
          <path d="M14 32 L 34 32 L 24 40 Z" fill="#FFD1D1"/>`
  },
  astro: {
    color: "#FF5D01",
    bg: "#FEEEDE",
    svg: `<path d="M24 4 L 40 42 L 32 42 L 24 24 L 16 42 L 8 42 Z" fill="#FF5D01"/>
          <ellipse cx="24" cy="36" rx="12" ry="4" fill="#000" opacity="0.7"/>`
  },
  telegram: {
    color: "#26A5E4",
    bg: "#E4F3FB",
    svg: `<circle cx="24" cy="24" r="20" fill="#26A5E4"/>
          <path d="M11 24 L 36 14 L 32 36 L 24 30 L 20 34 L 20 26 L 32 18 L 18 26 Z" fill="#fff"/>`
  },
  sqlite: {
    color: "#003B57",
    bg: "#E4EAEE",
    svg: `<ellipse cx="24" cy="12" rx="16" ry="5" fill="#003B57"/>
          <path d="M8 12 L 8 36 Q 8 41 24 41 Q 40 41 40 36 L 40 12" fill="#003B57"/>
          <ellipse cx="24" cy="22" rx="16" ry="4" fill="none" stroke="#fff" stroke-width="1.2" opacity="0.5"/>
          <ellipse cx="24" cy="32" rx="16" ry="4" fill="none" stroke="#fff" stroke-width="1.2" opacity="0.5"/>`
  },
  playwright: {
    color: "#2EAD33",
    bg: "#E6F5E7",
    svg: `<circle cx="24" cy="24" r="18" fill="#2EAD33"/>
          <text x="24" y="30" text-anchor="middle" font-family="Arial,sans-serif" font-size="18" font-weight="700" fill="#fff">▶</text>`
  },
  reportlab: {
    color: "#DC2626",
    bg: "#FEE5E5",
    svg: `<rect x="10" y="6" width="28" height="36" rx="2" fill="#fff" stroke="#DC2626" stroke-width="2"/>
          <text x="24" y="30" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" font-weight="700" fill="#DC2626">PDF</text>`
  },
  higgsfield: {
    color: "#9333EA",
    bg: "#F0E5FE",
    svg: `<circle cx="24" cy="24" r="18" fill="#9333EA"/>
          <path d="M16 16 L 16 32 M 32 16 L 32 32 M 16 24 L 32 24" stroke="#fff" stroke-width="3" stroke-linecap="round"/>`
  },
  veo3: {
    color: "#4285F4",
    bg: "#E8F0FE",
    svg: `<rect x="6" y="12" width="36" height="24" rx="4" fill="#4285F4"/>
          <path d="M20 18 L 32 24 L 20 30 Z" fill="#fff"/>
          <text x="24" y="45" text-anchor="middle" font-family="Arial,sans-serif" font-size="8" font-weight="700" fill="#4285F4">Veo3</text>`
  },
  scheduler: {
    color: "#6B7280",
    bg: "#F0F1F3",
    svg: `<circle cx="24" cy="24" r="18" fill="none" stroke="#6B7280" stroke-width="3"/>
          <path d="M24 12 L 24 24 L 32 28" stroke="#6B7280" stroke-width="3" stroke-linecap="round" fill="none"/>`
  },
  http: {
    color: "#6366F1",
    bg: "#E7E9FE",
    svg: `<circle cx="24" cy="24" r="18" fill="#6366F1"/>
          <text x="24" y="29" text-anchor="middle" font-family="Arial,sans-serif" font-size="11" font-weight="700" fill="#fff">HTTP</text>`
  },
  merge: {
    color: "#8B5CF6",
    bg: "#EEE5FE",
    svg: `<path d="M8 12 L 20 24 L 8 36 M 40 12 L 28 24 L 40 36" stroke="#8B5CF6" stroke-width="3" fill="none" stroke-linecap="round"/>
          <circle cx="24" cy="24" r="4" fill="#8B5CF6"/>`
  },
  filter: {
    color: "#0EA5E9",
    bg: "#DEF1FD",
    svg: `<path d="M6 8 L 42 8 L 30 24 L 30 40 L 18 34 L 18 24 Z" fill="#0EA5E9"/>`
  },
  jd_source: {
    color: "#6B7280",
    bg: "#F0F1F3",
    svg: `<rect x="10" y="6" width="28" height="36" rx="2" fill="#fff" stroke="#6B7280" stroke-width="2"/>
          <path d="M15 14 H 33 M15 20 H 33 M15 26 H 27 M15 32 H 30" stroke="#6B7280" stroke-width="1.6" stroke-linecap="round"/>`
  },
  wttj: {
    color: "#FF375E",
    bg: "#FDE4EA",
    svg: `<rect x="6" y="6" width="36" height="36" rx="4" fill="#FF375E"/>
          <text x="24" y="30" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" font-weight="700" fill="#fff">WTTJ</text>`
  },
  linkedin: {
    color: "#0A66C2",
    bg: "#E4EEF7",
    svg: `<rect x="4" y="4" width="40" height="40" rx="6" fill="#0A66C2"/>
          <text x="24" y="32" text-anchor="middle" font-family="Arial,sans-serif" font-size="20" font-weight="700" fill="#fff">in</text>`
  },
  france_travail: {
    color: "#000091",
    bg: "#E5E5F4",
    svg: `<rect x="6" y="6" width="36" height="36" rx="4" fill="#000091"/>
          <text x="24" y="28" text-anchor="middle" font-family="Arial,sans-serif" font-size="9" font-weight="700" fill="#fff">FR</text>
          <text x="24" y="38" text-anchor="middle" font-family="Arial,sans-serif" font-size="7" font-weight="700" fill="#fff">TRAVAIL</text>`
  },
  next_js: {
    color: "#000",
    bg: "#F0F0F0",
    svg: `<circle cx="24" cy="24" r="20" fill="#000"/>
          <text x="24" y="30" text-anchor="middle" font-family="Arial,sans-serif" font-size="16" font-weight="700" fill="#fff">N</text>`
  },
  react_email: {
    color: "#61DAFB",
    bg: "#E5F9FE",
    svg: `<circle cx="24" cy="24" r="4" fill="#61DAFB"/>
          <g stroke="#61DAFB" stroke-width="1.5" fill="none">
            <ellipse cx="24" cy="24" rx="18" ry="7"/>
            <ellipse cx="24" cy="24" rx="18" ry="7" transform="rotate(60 24 24)"/>
            <ellipse cx="24" cy="24" rx="18" ry="7" transform="rotate(120 24 24)"/>
          </g>`
  },
  chart: {
    color: "#6366F1",
    bg: "#E7E9FE",
    svg: `<rect x="6" y="6" width="36" height="36" rx="4" fill="none" stroke="#6366F1" stroke-width="2"/>
          <polyline points="10,34 18,26 26,30 34,16 40,20" stroke="#6366F1" stroke-width="2.5" fill="none" stroke-linecap="round"/>`
  },
  form: {
    color: "#EAB308",
    bg: "#FEF5CE",
    svg: `<rect x="8" y="6" width="32" height="36" rx="3" fill="#fff" stroke="#EAB308" stroke-width="2"/>
          <path d="M14 16 H 34 M14 22 H 30 M14 28 H 34 M14 34 H 26" stroke="#EAB308" stroke-width="1.8" stroke-linecap="round"/>`
  },
  upload: {
    color: "#0891B2",
    bg: "#DEF3F7",
    svg: `<path d="M24 32 L 24 8 M 16 16 L 24 8 L 32 16" stroke="#0891B2" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          <rect x="8" y="32" width="32" height="10" rx="2" fill="#0891B2"/>`
  }
};
