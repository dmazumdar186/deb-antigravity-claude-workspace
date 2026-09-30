// Vercel serverless function: receive proposal events, forward to Telegram
// Env vars required: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'method_not_allowed' });
  }

  const { slug, client, event, extra } = req.body || {};
  if (!slug || !event) {
    return res.status(400).json({ error: 'missing_fields' });
  }

  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID;
  if (!token || !chatId) {
    console.error('telegram env missing');
    return res.status(200).json({ ok: true, skipped: 'no_telegram_config' });
  }

  const ua = req.headers['user-agent'] || 'unknown';
  const ip = req.headers['x-forwarded-for']?.split(',')[0]?.trim() || req.headers['x-real-ip'] || 'unknown';
  const country = req.headers['x-vercel-ip-country'] || '??';
  const city = req.headers['x-vercel-ip-city'] || '';
  const loc = city ? `${decodeURIComponent(city)}, ${country}` : country;

  const icons = {
    opened: '📬',
    viewed: '👁',
    pay_clicked: '💳',
    signed: '✍️',
  };
  const icon = icons[event] || '•';
  const label = event === 'opened' ? 'Proposal first opened' :
                event === 'viewed' ? 'Proposal viewed again' :
                event === 'pay_clicked' ? 'Proposal — Pay clicked' :
                event === 'signed' ? 'Proposal SIGNED' : `Proposal — ${event}`;

  const ts = new Date().toLocaleString('en-US', { timeZone: 'UTC', dateStyle: 'short', timeStyle: 'short' });
  const extraLine = extra ? `\n<code>${extra}</code>` : '';
  const text = `${icon} <b>${label}</b>\n<b>${client || slug}</b>\n<code>/${slug}</code>${extraLine}\n\n<i>${loc} · ${ts} UTC</i>`;

  try {
    const r = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text, parse_mode: 'HTML', disable_web_page_preview: true }),
    });
    const data = await r.json();
    if (!data.ok) console.error('telegram error:', data);
    return res.status(200).json({ ok: data.ok });
  } catch (e) {
    console.error('telegram fetch failed:', e.message);
    return res.status(200).json({ ok: false, error: e.message });
  }
}
