// Vercel serverless function: receive a signed proposal PDF and deliver it to Telegram.
// The proposal page POSTs the generated PDF as a raw application/pdf body, with
// slug/client/name in the query string. We forward it as a Telegram document so the
// sender receives the actual signed file in one click.
//
// Env vars required: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

export const config = { api: { bodyParser: false } };

const MAX_BYTES = 5 * 1024 * 1024; // safety ceiling; client guards at ~4 MB

async function readRawBody(req) {
  if (Buffer.isBuffer(req.body)) return req.body;
  if (typeof req.body === 'string') return Buffer.from(req.body, 'binary');
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    const buf = typeof chunk === 'string' ? Buffer.from(chunk) : chunk;
    total += buf.length;
    if (total > MAX_BYTES) throw new Error('payload_too_large');
    chunks.push(buf);
  }
  return Buffer.concat(chunks);
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'method_not_allowed' });
  }

  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID;
  if (!token || !chatId) {
    console.error('telegram env missing');
    return res.status(200).json({ ok: false, skipped: 'no_telegram_config' });
  }

  const { slug = '', client = '', name = '' } = req.query || {};

  let buf;
  try {
    buf = await readRawBody(req);
  } catch (e) {
    const code = e.message === 'payload_too_large' ? 413 : 400;
    return res.status(code).json({ ok: false, error: e.message });
  }
  if (!buf || buf.length < 100) {
    return res.status(400).json({ ok: false, error: 'empty_body' });
  }

  const country = req.headers['x-vercel-ip-country'] || '??';
  let city = req.headers['x-vercel-ip-city'] || '';
  try { city = decodeURIComponent(city); } catch (e) { /* malformed geo header — keep raw */ }
  const loc = city ? `${city}, ${country}` : country;
  const ts = new Date().toLocaleString('en-US', { timeZone: 'UTC', dateStyle: 'short', timeStyle: 'short' });

  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const caption =
    `✅ <b>Proposal ACCEPTED & SIGNED</b>\n` +
    `<b>${esc(client || slug)}</b>\n` +
    `<code>/${esc(slug)}</code>\n` +
    `Signed by: <b>${esc(name) || 'unknown'}</b>\n\n` +
    `<i>${esc(loc)} · ${ts} UTC</i>`;

  const filename = `${String(slug || 'proposal').replace(/[^a-z0-9_-]/gi, '_')}_signed.pdf`;

  try {
    const form = new FormData();
    form.append('chat_id', chatId);
    form.append('caption', caption);
    form.append('parse_mode', 'HTML');
    form.append('document', new Blob([buf], { type: 'application/pdf' }), filename);

    const r = await fetch(`https://api.telegram.org/bot${token}/sendDocument`, {
      method: 'POST',
      body: form,
    });
    const data = await r.json();
    if (!data.ok) {
      console.error('telegram sendDocument error:', data);
      return res.status(200).json({ ok: false, error: 'telegram_failed' });
    }
    return res.status(200).json({ ok: true });
  } catch (e) {
    console.error('submit failed:', e.message);
    return res.status(200).json({ ok: false, error: e.message });
  }
}
