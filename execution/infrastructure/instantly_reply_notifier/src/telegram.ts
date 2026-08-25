/**
 * Send a Telegram message via Bot API (HTML parse mode).
 *
 * Throws on failure. The caller MUST surface that: this worker exists so a
 * reply reaches a phone, so a swallowed send error is the one failure mode
 * that makes the whole thing pointless while still looking healthy.
 * Retries once on 5xx / network error (Telegram has brief blips); a 4xx is a
 * config problem (bad token, chat not found) and is not worth retrying.
 */
export async function sendTelegramMessage(
  botToken: string,
  chatId: string,
  message: string
): Promise<void> {
  if (!botToken || !chatId) {
    throw new Error("Telegram not configured: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing");
  }

  const url = `https://api.telegram.org/bot${botToken}/sendMessage`;
  const payload = JSON.stringify({ chat_id: chatId, text: message, parse_mode: "HTML" });

  let lastErr = "";

  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
      });

      if (resp.ok) return;

      const text = await resp.text();
      lastErr = `HTTP ${resp.status}: ${text}`;
      console.error(`[Telegram] Send failed (attempt ${attempt}) - ${lastErr}`);

      // 4xx is a config error - retrying sends the same broken request again.
      if (resp.status >= 400 && resp.status < 500) break;
    } catch (err) {
      lastErr = String(err);
      console.error(`[Telegram] Network error (attempt ${attempt}): ${lastErr}`);
    }

    if (attempt === 1) await new Promise((r) => setTimeout(r, 500));
  }

  throw new Error(`Telegram send failed: ${lastErr}`);
}

export interface ReplyData {
  name: string;
  email: string;
  company: string;
  campaign: string;
  subject: string;
  replySnippet: string;
  category: string;
  autoReplied?: boolean;
  /** Set only for secondary Instantly accounts (e.g. a client's). Renders a bold banner above everything else so it can never be mistaken for your own account. */
  accountLabel?: string;
}

export function buildTelegramMessage(data: ReplyData): string {
  let emoji = "📩";
  let label = "New Reply";

  if (data.category === "booking_ready") {
    emoji = "🔥";
    label = "Booking Ready";
  } else if (data.category === "positive") {
    emoji = "✅";
    label = "Positive Reply";
  } else if (data.category === "neutral") {
    emoji = "💬";
    label = "Reply (Ambiguous - Check It)";
  } else if (data.category === "unknown") {
    emoji = "❓";
    label = "Unclassified Reply";
  }

  if (data.autoReplied) {
    emoji = "🤖";
    label = `Auto-Replied (${label})`;
  }

  const subjectLine = data.subject ? `\n<b>Subject:</b> ${escapeHtml(data.subject)}` : "";
  const accountBanner = data.accountLabel ? `🏢 <b>${escapeHtml(data.accountLabel.toUpperCase())}</b> 🏢\n\n` : "";

  return (
    accountBanner +
    `${emoji} <b>${label}</b>\n\n` +
    `<b>Lead:</b> ${escapeHtml(data.name)}\n` +
    `<b>Email:</b> ${escapeHtml(data.email)}\n` +
    `<b>Company:</b> ${escapeHtml(data.company)}\n` +
    `<b>Campaign:</b> ${escapeHtml(data.campaign)}` +
    subjectLine +
    `\n\n<b>Reply:</b>\n${escapeHtml(data.replySnippet)}`
  );
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
