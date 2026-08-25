/**
 * Hybrid classifier for Instantly reply notifications.
 * Layer 1: Rules (OOO, not_interested, booking_ready) - fast, no cost
 * Layer 2: GPT-4o-mini via OpenRouter for unknowns - ~$0.001/call
 * Fail open: if LLM errors, treat as positive (notify anyway).
 */

export type Category = "ooo" | "not_interested" | "booking_ready" | "positive" | "negative" | "neutral" | "unknown";

export interface ClassifyResult {
  category: Category;
  confidence: number;
  method: "rules" | "llm" | "failopen";
}

// --- OOO patterns ---
// Multi-word phrases - safe to match as plain substrings.
const OOO_PATTERNS = [
  "out of office",
  "automatic reply",
  "auto-reply",
  "autoreply",
  "currently away",
  "maternity leave",
  "paternity leave",
  "be back on",
  "returning on",
  "away until",
  "away from the office",
];

// Short or ambiguous OOO markers that MUST be word-bounded. An OOO match is a
// silent drop - the operator never learns the reply existed - so anything that
// can appear inside an ordinary word or phrase belongs here, not above.
const OOO_REGEXES: RegExp[] = [
  // Bare "ooo" as a substring also matches "sooo", "loool", "goood",
  // i.e. exactly the enthusiastic replies this tool exists to surface.
  /\booo\b/i,
  // "return on" is an OOO marker ("I return on Monday") and a sales term
  // ("the return on investment"). Exclude the money sense.
  // "vacation" alone hits travel-industry leads ("dream vacation homes").
  /\b(on|for) vacation\b|\bvacation until\b/i,
  // "on leave" alone hits HR-tech leads ("leave management software").
  /\bon ((parental|maternity|paternity|sick|annual|study) )?leave\b(?!\s+(management|policy|software|tracking|system|balance))/i,
  // "limited access" alone hits budget talk ("limited access to budget, but curious").
  /\blimited access to (my )?(email|e-mail|inbox|internet|wifi|phone)\b/i,
  /\breturn on\b(?!\s+(investment|invest|ad ?spend|equity|capital|marketing))/i,
];

// --- Negative / not-interested patterns ---
const NOT_INTERESTED_PATTERNS: RegExp[] = [
  // Original n8n patterns
  /\b(not interested)\b/i,
  /\b(no thanks?)\b/i,
  /\b(remove me)\b/i,
  /\b(unsubscribe)\b/i,
  /\b(stop email(ing)?)\b/i,
  /\b(opt out|opt-out)\b/i,
  /\b(do not contact)\b/i,
  // "I'll pass this along to our VP" is a forward, often the start of a deal.
  /\b(i'?ll|i) pass\b(?!\s+(this|it|that|along|on to|to))/i,
  /\bpass on this\b/i,
  /\b(leave me alone)\b/i,
  /\b(don'?t like to be pressured)\b/i,
  /\b(cold emails do not work)\b/i,
  // Standalone removal words (the "REMOVE" bug fix) - `m` flag matches per-line, catches signature-appended replies
  /^(remove|stop|delete|unsubscribe|no)\s*$/im,
  // Common declines
  /\b(not for us)\b/i,
  // Bare "we're good/set" also ends booking confirmations ("we're all set for
  // the call", "we're good to go, what time Tuesday?"). Exclude the scheduling sense.
  /\bwe'?re (all set|good|covered|set)\b(?!\s*(to go|for\b|,?\s*(what|when|let'?s|lets|monday|tuesday|wednesday|thursday|friday)))/i,
  // Only the "already have a vendor" sense - not "already have budget approved".
  /\balready have\b\s+(a |an |our )?(vendor|supplier|provider|solution|agency|partner|tool|system|someone|somebody|team|one)\b/i,
  /\b(not looking)\b/i,
  // "no need to explain further, let's set up a call" is not a decline.
  /\bno need\b[,.]?\s*(thanks|thank you|for now|at this time|at the moment|we\b)/i,
  /\b(not at this time)\b/i,
  // "please don't hesitate to reach out" is an invitation, not a decline.
  /\bplease don'?t (contact|email|e-mail|reach out|call|message|write|send|follow up)\b/i,
  /\b(wrong person)\b/i,
  /\b(not the right (fit|person|time))\b/i,
  /\b(take me off)\b/i,
  /\bdon'?t (email|contact|message) (me|us)\b/i,
  /\b(not a good fit)\b/i,
  /\b(we handle this internally)\b/i,
  /\b(please remove)\b/i,
  /\b(not interested in)\b/i,
];

// --- Booking / positive patterns ---
const BOOKING_PATTERNS: RegExp[] = [
  /\b(let'?s\s+(meet|chat|talk|connect|discuss|hop on|jump on|set up|schedule|have a meeting))/i,
  /\b(let\s+us\s+(meet|chat|talk|connect|discuss))\b/i,
  /\b(when\s+(are you|can we|do you|is a good|works for))/i,
  /\b(i('?m| am)\s+(free|available|open))\b/i,
  /\b(give me a call)\b/i,
  /\b(have time right now)\b/i,
  /\b(call me|phone me)\b/i,
  /\b(booked for)\b/i,
  /\b(schedule a call)\b/i,
  /\b(what times? work)\b/i,
  /\b(how'?s?\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b/i,
  /\b(how about\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|next week))\b/i,
  /\b(we should connect)\b/i,
  /\bwhen\s+.{0,10}\s*available\b/i,
  /\blmk\s+when\b/i,
  /\b(at\s+)?\d{1,2}(:\d{2})?\s*(am|pm)\b/i,
  /\b\d{3}[.\-\s]?\d{3}[.\-\s]?\d{4}\b/,
  /\b(interested|sounds good|sounds interesting|tell me more|would love to|keen to|happy to chat)\b/i,
  // Note: "yes/sure/absolutely" intentionally excluded - too broad, causes false positives on removal replies
];

// Negative modifiers that cancel a booking pattern match
const BOOKING_NEGATORS = ["but don't", "but i don't", "no thanks", "not interested", "pass", "not looking"];

export function classifyByRules(replyText: string, isAutoReply: boolean): ClassifyResult | null {
  const lower = replyText.toLowerCase();

  // OOO check
  if (
    isAutoReply ||
    OOO_PATTERNS.some((p) => lower.includes(p)) ||
    OOO_REGEXES.some((r) => r.test(replyText))
  ) {
    return { category: "ooo", confidence: 1.0, method: "rules" };
  }

  // Not interested check
  for (const pat of NOT_INTERESTED_PATTERNS) {
    if (pat.test(replyText)) {
      return { category: "not_interested", confidence: 1.0, method: "rules" };
    }
  }

  // Booking check
  const hasNegator = BOOKING_NEGATORS.some((neg) => lower.includes(neg));
  if (!hasNegator) {
    for (const pat of BOOKING_PATTERNS) {
      if (pat.test(replyText)) {
        return { category: "booking_ready", confidence: 0.95, method: "rules" };
      }
    }
  }

  // Unknown - needs LLM
  return null;
}

export async function classifyByLlm(
  replyText: string,
  openrouterApiKey: string
): Promise<ClassifyResult> {
  // The cost of the two errors is wildly asymmetric. A false "positive" costs the
  // operator two seconds of reading a dud. A false "negative" means a real lead is
  // silently dropped and never seen again. So "negative" is deliberately narrow:
  // an explicit request to stop, or an explicit decline. Everything short of that
  // - annoyance, suspicion, blunt questions - is neutral and reaches the phone.
  const prompt = `You are triaging a reply to a cold email. Your only job is to decide whether a human needs to read it.

Reply text:
"""
${replyText.substring(0, 500)}
"""

Classify as exactly one of:
- "positive": Interested, open to talking, asking about the offer, or responding constructively.
- "negative": ONLY when the person explicitly asks to stop being contacted or explicitly declines. Examples: "remove me", "unsubscribe", "not interested", "we already have a vendor", "stop emailing me".
- "neutral": Everything else. This includes suspicious, annoyed, blunt, confused, or terse replies that do NOT explicitly decline. "Who is this?", "How did you get my email?", "What is this about?", "?" are ALL neutral - the person is still engaging and a human must see it.

Critical: annoyance is NOT a decline. If the person is irritated but has not asked to be removed or said no, classify neutral, never negative. When genuinely torn between negative and neutral, choose neutral.

Return only valid JSON: {"category": "positive"|"negative"|"neutral", "confidence": 0.0-1.0}`;

  try {
    const resp = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${openrouterApiKey}`,
        "HTTP-Referer": "https://example.com",
        "X-Title": "Instantly Reply Notifier",
      },
      body: JSON.stringify({
        model: "openai/gpt-4o-mini",
        temperature: 0.3,
        messages: [{ role: "user", content: prompt }],
        response_format: { type: "json_object" },
      }),
    });

    if (!resp.ok) {
      const errText = await resp.text();
      console.error(`[LLM] OpenRouter error ${resp.status}: ${errText}`);
      return { category: "unknown", confidence: 0, method: "failopen" };
    }

    const data = (await resp.json()) as {
      choices: Array<{ message: { content: string } }>;
    };
    const content = data.choices?.[0]?.message?.content ?? "{}";
    const parsed = JSON.parse(content) as { category?: string; confidence?: number };

    // Validate before casting
    const rawCat = parsed.category;
    if (!rawCat || !["positive", "negative", "neutral"].includes(rawCat)) {
      return { category: "unknown", confidence: 0, method: "failopen" };
    }

    return {
      category: rawCat as Category,
      confidence: typeof parsed.confidence === "number" ? parsed.confidence : 0.8,
      method: "llm",
    };
  } catch (err) {
    console.error("[LLM] Classification failed (network/parse error):", String(err));
    // Return explicit "error" via failopen - shouldNotify will still notify to avoid silent drops
    return { category: "unknown", confidence: 0, method: "failopen" };
  }
}

export function shouldNotify(result: ClassifyResult): boolean {
  return (
    result.category === "booking_ready" ||
    result.category === "positive" ||
    result.category === "neutral" || // ambiguous/questions - human needs to see these too
    result.category === "unknown" // fail open
  );
}
