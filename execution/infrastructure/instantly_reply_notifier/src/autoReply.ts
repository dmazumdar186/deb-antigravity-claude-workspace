/**
 * Campaign-scoped auto-reply (OPTIONAL, OFF BY DEFAULT).
 *
 * When a positive / booking-ready reply lands on a whitelisted campaign, this
 * sends a fixed template reply via the Instantly API, in the same thread, from
 * the same sending mailbox - with NO human approval.
 *
 * !! READ THIS BEFORE YOU ENABLE IT !!
 * This shipped once and misfired: Instantly's `GET /api/v2/emails?search=<lead>`
 * does NOT actually filter by lead (verified live - two different `search` values
 * returned identical result sets). The code below takes the most recent *received*
 * email in the campaign, which can be a DIFFERENT lead's thread. The result was an
 * automated pitch landing inside a real, months-old human conversation.
 *
 * Before enabling, add at minimum:
 *   1. A hard identity check: compare the resolved record's recipient against the
 *      webhook's `lead_email` and ABORT on mismatch (fail closed).
 *   2. A dry-run mode that logs the resolved {id, eaccount, recipient} instead of sending.
 *   3. A test on a dedicated throwaway campaign with no overlapping leads -
 *      never a fake lead inside a live campaign.
 * Notifications work fine without any of this. Leaving AUTO_REPLY_CAMPAIGNS empty
 * disables the whole path.
 */

// Campaign IDs that get an auto-sent template reply. Empty = feature disabled.
// Example: { "your-campaign-uuid": "My Campaign Name" }
export const AUTO_REPLY_CAMPAIGNS: Record<string, string> = {};

// Your booking link, used in the template below.
const BOOKING_LINK = "https://cal.com/your-handle/15min";

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Replace this with your own copy before enabling anything.
function renderBody(name: string): string {
  return `thanks for the reply, ${name}.

quick rundown: [one or two lines on what you do and what the offer is].

if you'd rather just grab time now, here's my calendar:
${BOOKING_LINK}

talk soon,
[your name]`;
}

export function buildAutoReplyBody(firstName: string): { text: string; html: string } {
  const name = firstName || "there";
  const text = renderBody(name);
  const htmlSource = renderBody(escapeHtml(name));

  const html = htmlSource
    .split("\n\n")
    .map((para) => `<div>${para.replace(/\n/g, "<br>")}</div>`)
    .join("<div><br></div>");

  return { text, html };
}

export interface EmailRecord {
  id: string;
  eaccount: string;
}

/**
 * Look up the reply email's id + sending mailbox (eaccount) so the auto-reply
 * threads correctly. Explicitly filters to received (lead-authored) emails and
 * sorts client-side by timestamp - the API does not guarantee item order, and
 * a thread can contain the original outbound, follow-ups, and the reply, any
 * of which could otherwise be picked as items[0].
 *
 * WARNING: `search=` is unreliable (see the file header). Add a recipient
 * identity check here before trusting the result for a real send.
 */
export async function fetchLatestEmailRecord(
  campaignId: string,
  leadEmail: string,
  apiKey: string
): Promise<EmailRecord | null> {
  const url = `https://api.instantly.ai/api/v2/emails?campaign_id=${encodeURIComponent(
    campaignId
  )}&search=${encodeURIComponent(leadEmail)}&email_type=received&limit=10`;

  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${apiKey}` },
  });

  if (!resp.ok) {
    console.error(`[autoReply] Email lookup failed (${resp.status}): ${await resp.text()}`);
    return null;
  }

  const data = (await resp.json()) as {
    items?: Array<{ id?: string; eaccount?: string; timestamp_email?: string }>;
  };
  const items = (data.items ?? []).filter((i) => i.id && i.eaccount);
  if (items.length === 0) {
    console.error("[autoReply] Email lookup returned no received items with id/eaccount");
    return null;
  }

  items.sort((a, b) => (b.timestamp_email ?? "").localeCompare(a.timestamp_email ?? ""));
  const latest = items[0];

  return { id: latest.id as string, eaccount: latest.eaccount as string };
}

export async function sendAutoReply(
  record: EmailRecord,
  subject: string,
  body: { text: string; html: string },
  apiKey: string
): Promise<boolean> {
  const resp = await fetch("https://api.instantly.ai/api/v2/emails/reply", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      reply_to_uuid: record.id,
      eaccount: record.eaccount,
      subject,
      body,
    }),
  });

  if (!resp.ok) {
    console.error(`[autoReply] Send failed (${resp.status}): ${await resp.text()}`);
    return false;
  }

  return true;
}
