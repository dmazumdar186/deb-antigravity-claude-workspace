// HTML widget renderer — Vapi Web SDK on a single page, one button.
// Inlined here so the Worker has zero external assets to bundle.

export function renderWidget(args: {
  publicKey: string;
  assistantId: string;
  clinicName: string;
}): string {
  const { publicKey, assistantId, clinicName } = args;
  const safe = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  return `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${safe(clinicName)} — assistant vocal IA</title>
<style>
  :root { color-scheme: light; }
  html, body { margin:0; height:100%; font:16px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; color:#1c1c1c; background:#f6f3ee; }
  main { max-width: 540px; margin: 0 auto; padding: 24px 20px 80px; }
  h1 { margin:0 0 4px; font-size: 22px; letter-spacing:-0.01em; }
  p.lede { margin:0 0 18px; color:#5b5b58; font-size:14px; }
  .banner { background:#fff5cf; border:1px solid #efd061; padding:10px 12px; border-radius:8px; font-size:13px; color:#5a4500; margin-bottom:18px; }
  button.cta { display:flex; align-items:center; justify-content:center; gap:10px; width:100%; padding:18px 20px; border:0; border-radius:14px; background:#0b3d2e; color:#fff; font-size:17px; font-weight:600; cursor:pointer; }
  button.cta:disabled { opacity:0.55; cursor:default; }
  button.cta.active { background:#a8120c; }
  .dot { width:10px; height:10px; border-radius:50%; background:#fff; opacity:0.6; }
  button.cta.active .dot { animation: pulse 1.1s ease-in-out infinite; }
  @keyframes pulse { 0%,100%{opacity:0.35} 50%{opacity:1} }
  .status { margin-top:14px; font-size:13px; color:#666; min-height:20px; }
  .transcript { margin-top:18px; }
  .turn { padding:10px 12px; margin:6px 0; border-radius:10px; font-size:14px; line-height:1.45; }
  .turn.you { background:#e9efe7; }
  .turn.lisa { background:#fff; border:1px solid #e6e2d8; }
  .turn .who { display:block; font-size:11px; text-transform:uppercase; letter-spacing:0.05em; color:#888; margin-bottom:2px; }
  .toolcall { background:#eef3f7; color:#274058; padding:8px 10px; border-radius:8px; font-size:12px; margin:6px 0; font-family: ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
  footer { margin-top:34px; font-size:12px; color:#8a8a86; }
</style>
</head>
<body>
<main>
  <h1>${safe(clinicName)} — Lisa, AI assistant</h1>
  <p class="lede">Voice agent demo. Click the button, speak in English.</p>
  <div class="banner">⚠️ Demo — simulated data. Appointments are created in a Cal.com test calendar, not the real clinic's.</div>

  <button class="cta" id="talk" type="button" disabled>
    <span class="dot"></span>
    <span id="talk-label">Loading…</span>
  </button>
  <div class="status" id="status">Initializing Vapi SDK…</div>

  <div class="transcript" id="transcript"></div>

  <footer>
    Construit par <a href="https://prodcraft.fyi">prodcraft.fyi</a> — Vapi + Gemini 3.1 Flash Live + Cal.com. RGPD : aucune donnée patient en démo ; hébergement HDS en production.
  </footer>
</main>

<script type="module">
import Vapi from "https://esm.sh/@vapi-ai/web@2";

const PUBLIC_KEY = ${JSON.stringify(publicKey)};
const ASSISTANT_ID = ${JSON.stringify(assistantId)};

const talkBtn = document.getElementById('talk');
const talkLabel = document.getElementById('talk-label');
const statusEl = document.getElementById('status');
const transcriptEl = document.getElementById('transcript');

function setStatus(t) { statusEl.textContent = t; }
function pushTurn(who, text, klass) {
  const div = document.createElement('div');
  div.className = klass;
  const w = document.createElement('span'); w.className = 'who'; w.textContent = who;
  div.appendChild(w);
  div.appendChild(document.createTextNode(text));
  transcriptEl.appendChild(div);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

if (!PUBLIC_KEY || !ASSISTANT_ID || ASSISTANT_ID === "pending") {
  setStatus("Configuration incomplète : VAPI_PUBLIC_KEY ou VAPI_ASSISTANT_ID manquant côté serveur.");
} else {
  const vapi = new Vapi(PUBLIC_KEY);
  let active = false;

  vapi.on('call-start', () => {
    active = true;
    talkBtn.classList.add('active');
    talkLabel.textContent = 'Hang up';
    setStatus('Connected. Speak naturally.');
  });
  vapi.on('call-end', () => {
    active = false;
    talkBtn.classList.remove('active');
    talkLabel.textContent = 'Talk to Lisa';
    setStatus('Call ended.');
  });
  vapi.on('message', (m) => {
    if (m.type === 'transcript' && m.transcriptType === 'final') {
      if (m.role === 'user') pushTurn('vous', m.transcript, 'turn you');
      if (m.role === 'assistant') pushTurn('Lisa', m.transcript, 'turn lisa');
    }
    if (m.type === 'tool-calls' && Array.isArray(m.toolCallList)) {
      for (const tc of m.toolCallList) {
        const d = document.createElement('div'); d.className = 'toolcall';
        d.textContent = 'tool · ' + (tc.function?.name || '?') + '(' + (tc.function?.arguments || '') + ')';
        transcriptEl.appendChild(d);
      }
    }
  });
  vapi.on('error', (err) => setStatus('Erreur : ' + (err?.message || err)));

  talkBtn.disabled = false;
  talkLabel.textContent = 'Talk to Lisa';
  setStatus('Ready. Click to start.');

  talkBtn.addEventListener('click', async () => {
    if (active) { vapi.stop(); return; }
    try { await vapi.start(ASSISTANT_ID); }
    catch (e) { setStatus('Impossible de démarrer : ' + (e?.message || e)); }
  });
}
</script>
</body>
</html>`;
}
