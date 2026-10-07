// useJevIcon: live icon suggestion from what the user types (use case 17).
// Not compiled in this repo; copy into an app repo. Python twin: execution/mobile_apps/jev_icon_pick.py
//
// KEY HANDLING: never put the OpenRouter key in the app bundle (it ships in plain text).
// Point JEV_URL at your own proxy that injects the key server-side and forwards to
// https://openrouter.ai/api/alpha/decisions. The workspace proxy is
// execution/infrastructure/api-proxy/ (AM-locked, see CLAUDE.local.md: do not clone or edit it;
// ask for a route there). Directive: directives/mobile_apps/jev_icon_pick.md
import { useEffect, useState } from "react";

const JEV_URL = "https://YOUR-PROXY.example.com/jev/decisions"; // proxy, never openrouter.ai directly
const BATCH = 39; // + `none` = 40 options per call

export type IconSet = Record<string, string>; // name -> one-line description
export type IconPick = { icon: string; probability: number };

async function ask(text: string, icons: IconSet, names: string[], signal: AbortSignal): Promise<Record<string, number>> {
  const criteria: Record<string, string> = { none: "no icon fits; the text is unrelated to every listed icon" };
  names.forEach((n) => (criteria[n] = icons[n]));
  const res = await fetch(JEV_URL, {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "typesafe/jev-1.13",
      state: { app: "habit app icon picker", user_typed: text },
      questions: { icon: { type: "choice", criteria,
        instructions: "Which icon best represents what the user typed? Judge by meaning, not by shared words." } },
    }),
  });
  if (!res.ok) throw new Error(`jev ${res.status}`);
  const data = await res.json();
  return data?.answers?.icon?.probabilities ?? {};
}

const rank = (p: Record<string, number>, icons: IconSet) =>
  Object.keys(p).filter((k) => k in icons).sort((a, b) => p[b] - p[a]);

export function useJevIcon(text: string, icons: IconSet, minConfidence = 0.4): IconPick[] {
  const [picks, setPicks] = useState<IconPick[]>([]);
  useEffect(() => {
    const q = text.trim();
    if (q.length < 3) { setPicks([]); return; }
    const ctrl = new AbortController(); // aborts the in-flight call when the user keeps typing
    const timer = setTimeout(async () => {
      try {
        const names = Object.keys(icons);
        const batches = Array.from({ length: Math.ceil(names.length / BATCH) }, (_, i) => names.slice(i * BATCH, (i + 1) * BATCH));
        const all = await Promise.all(batches.map((b) => ask(q, icons, b, ctrl.signal)));
        const p = all.length === 1 ? all[0]
          : await ask(q, icons, all.flatMap((x) => rank(x, icons).slice(0, 3)), ctrl.signal);
        const top = rank(p, icons).slice(0, 3);
        setPicks(top.length && p[top[0]] >= minConfidence ? top.map((icon) => ({ icon, probability: p[icon] })) : []);
      } catch {
        if (!ctrl.signal.aborted) setPicks([]); // fail open: no suggestion, the user picks manually
      }
    }, 250);
    return () => { clearTimeout(timer); ctrl.abort(); };
  }, [text, icons, minConfidence]);
  return picks;
}
