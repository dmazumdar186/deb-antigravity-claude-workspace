"""GTM-pipeline copy for the DMC / Fitout / EventAV campaigns (10 Nov 2026), spintax on every line, Jev humanizer gate.

description: Builds copy_gtm.json (one block per niche) selling ProdCraft GTM pipelines to event production/AV,
             commercial fit-out and incentive travel/DMC firms; renders every spin N ways and scores each with Jev.
inputs: --renders N; --approved (operator sign-off only); env OPENROUTER_API_KEY (Jev)
outputs: copy_gtm.json next to this script; stdout score table; .tmp/jev_ledger.jsonl row
usage:
    python3 execution/lead_sourcing/prodcraft_campaign/build_copy_gtm.py --renders 16
Directive: directives/lead_sourcing/prodcraft_campaign.md (section "GTM v3")

Sources (grounding):
- Proof: deliverables/linkedin_videos/gtm_pipeline_2026-11-10/FACTS.md + directives/gtm_client_workflows/
  accessory_masters_prd.md (client buys small businesses; ~a dozen emails a day by hand -> ~800/day across 32 inboxes;
  addresses verified before sending; AI sorts replies; hot lead pings the phone, a person takes over; interested
  gets an auto-reply asking for a call; interested leads into the CRM). "$128K in 4 months" is NOT used in the
  emails: FACTS.md says it is a client revenue increase not credited to the system alone.
- Video page: https://prodcraft.fyi/gtm (31.75 s, credit line removed per operator 2026-11-10).
- Offer (operator 2026-11-10: not 50; 'do what the research says'): step 1 free first 20 named contacts, emails checked, yes/no; step 3 the prospect names a number; no guarantee (no data).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
from execution.lead_sourcing.recruiter_campaign.build_copy import R, render  # noqa: E402
from execution.modules import jev_client as jev  # noqa: E402

VIDEO = "https://prodcraft.fyi/new-clients"  # 301 -> /gtm/ (plain-word link; "gtm" read as jargon)
NICHE = {
    "EventAV": dict(buyers="brands and agencies planning events", work="event work",
                    target="marketing and event leads at companies near you that run conferences and launches",
                    buyer_q="companies that run conferences, launches and brand events"),
    "Fitout": dict(buyers="companies planning an office move or refit", work="fit-out work",
                   target="office managers and ops heads at companies near you planning an office move",
                   buyer_q="companies planning an office move, expansion or refit"),
    "DMC": dict(buyers="companies planning incentive trips and offsites", work="incentive trip business",
                target="sales and hr leads at companies near you that run incentive trips",
                buyer_q="companies that run incentive trips, offsites and sales kick-offs"),
}
GREET = R("hey {{firstName}},", "hi {{firstName}},", "{{firstName}},")


def subjects(n: str) -> list[str]:
    return [R("new clients for {{companyName}}", "{{companyName}} pipeline", "{{firstName}}, new clients?"),
            R("your next client", "more corporate clients", "{{firstName}}, quick one")]


def pers_pain(n: str) -> str:
    """Personal hook + pain in one line (keeps step 1 near the 25-75 word range the research found best)."""
    w = NICHE[n]["work"]
    return R(f"saw {{{{project_reference}}}} on your site. guessing most new {w} still comes from referrals?",
             f"noticed {{{{project_reference}}}} on your site. guessing referrals still bring in most new {w}?",
             f"saw {{{{project_reference}}}} on your site. is most new {w} still coming from referrals?")


def pain(n: str) -> str:
    w = NICHE[n]["work"]
    return R(f"guessing most new {w} still comes from referrals and repeat clients?",
             f"my guess is new {w} still mostly comes through referrals.",
             f"bet most of your {w} still comes from people who already know you.")


PROOF = [R("this year i built this for a company that buys small businesses. about a dozen emails a day by hand became 800 a day.",
           "earlier this year i set this up for a firm that buys small businesses. they went from roughly 12 emails a day by hand to 800 a day.",
           "this year i built it for a company that buys small businesses: from about a dozen emails a day, by hand, to 800 a day.")]


# Offer (2026-11-10 research, 85M-email 30MPC/Gong data: a concrete offer CTA beats interest/meeting asks; most
# yeses go to a concrete sample). Operator: no 50; size 20 chosen (no data on N; a named, specific list is the lever).
def offer_q(n: str) -> str:
    tg = NICHE[n]["target"]
    return R(f"want me to pull the first 20 for you? {tg}, emails checked.",
             f"want me to find you 20 to start? {tg}, emails checked.",
             f"want a first list of 20? {tg}, emails checked.")


FREE = R("free, no call needed. just reply yes.", "it's free and there's no call. just reply yes.",
         "free, no call. a yes is all i need.")


def step1(n: str, personalized: bool) -> str:
    lines = [GREET, pers_pain(n) if personalized else pain(n)] + PROOF + [offer_q(n), FREE]
    return "\n\n".join(lines)


def step2(n: str) -> str:
    return "\n\n".join([
        R("{{firstName}}, here's a 30 second video of how it works:",
          "{{firstName}}, made a quick 30 second video of how it works:",
          "here's a 30 second video of how it works, {{firstName}}:"),
        R(VIDEO, f"{VIDEO} (30 sec)", f"video: {VIDEO}"),
        R("it finds the right people, checks each email address, then sends from lots of email accounts every day.",
          "it finds the right people, checks every email before sending, then sends a few a day from lots of addresses.",
          "it finds the people, checks each email first, then sends every day from lots of email addresses."),
        R("you only see the replies worth answering, and the best ones ping your phone.",
          "replies get sorted for you. when someone's keen, your phone pings and you take it from there.",
          "you get the good replies, and your phone pings when someone's ready to talk."),
        R("worth a look?", "worth 30 seconds?", "want me to set one up for you?")])


def step3(n: str) -> str:
    # Research: change of angle in the last step; the prospect names the number (no data either way, opinion).
    return "\n\n".join([
        R("last one, {{firstName}}.", "last note from me, {{firstName}}.", "{{firstName}}, last one."),
        R("different question: how many new clients a month would actually move the needle for {{companyName}}?",
          "different question: how many new clients a month would make a real difference for {{companyName}}?",
          "one question: how many new clients a month would actually matter for {{companyName}}?"),
        R("give me a number and i'll show you what it'd take.", "send me a number and i'll show you what it would take.",
          "reply with a number and i'll show you what it'd take."),
        R("if it's not a priority right now, say so and i'll stop.", "if now's not the time, tell me and i'll stop.",
          "and if it's not a priority, say so and i'll leave you alone.")])


def copy_for(n: str) -> dict:
    return {"niche": n, "subjects": subjects(n), "step1_personalized": step1(n, True),
            "step1_nopersonalization": step1(n, False), "step2": step2(n), "step3": step3(n)}


def lint(c: dict) -> list[str]:
    bad = [f"{k}: {line[:60]}" for k in ("step1_personalized", "step1_nopersonalization", "step2", "step3")
           for line in c[k].split("\n\n") if "{{RANDOM|" not in line]
    return bad + [f"subject: {s}" for s in c["subjects"] if "{{RANDOM|" not in s]


Q = {"human": jev.noul("Does this cold email read like one real person typed it quickly by hand?",
                       "true when casual, plain, specific",
                       "false when polished, generic or AI-written ('most X I talk to', 'leverage', 'streamline')"),
     "slop": jev.noul("Does this email contain generic AI-written sales cliches or filler?",
                      "true when stock phrases or flattery", "false when every sentence is concrete"),
     "pain": jev.noul("Does the email name a concrete problem this buyer (owner of an events, fit-out or travel firm) "
                      "has in winning new clients?",
                      "true when it names a specific struggle (depending on referrals, waiting for RFPs, no outbound)",
                      "false when it only describes the sender or a generic offer"),
     "fit": jev.noul("Does every proof or offer line directly support solving that buyer's problem of winning clients?",
                     "true when the offer and proof are about finding new clients", "false when a line is unrelated"),
     "plain": jev.noul("Would a non-technical company owner understand every sentence without software jargon? "
                       "Everyday words of their own industry (fit-out, refit, incentive trip, offsite, DMC, AV, launch) "
                       "count as plain (same rule as the 2 Nov build_copy_v2 gate).",
                       "true when plain words an owner uses",
                       "false when it uses terms like AI pipeline, workflow automation, API, enrichment, LLM")}
GATE = {"human": 0.70, "pain": 0.55, "fit": 0.55, "plain": 0.70}
SAMPLE = {"firstName": "Sarah", "companyName": "Northlight", "project_reference": "the Kraken ScreamFest launch"}


def main() -> None:
    ap = argparse.ArgumentParser(description="Build + Jev-gate GTM copy for DMC/Fitout/EventAV")
    ap.add_argument("--renders", type=int, default=12)
    ap.add_argument("--approved", action="store_true", help="mark operator-approved (only on the operator's word)")
    a = ap.parse_args()
    rng = random.Random(7)
    states, labels, out = [], [], {}
    for n in NICHE:
        c = copy_for(n)
        if (bad := lint(c)):
            sys.exit(f"spintax lint failed for {n}: {bad}")
        out[n] = c
        for key in ("step1_personalized", "step1_nopersonalization", "step2", "step3"):
            for _ in range(a.renders):
                states.append({"email": render(c[key], SAMPLE, rng)})
                labels.append((n, key))
    rs = jev.decide_many(states, Q, workers=8)
    cost, agg = 0.0, {}
    for lab, r, s in zip(labels, rs, states):
        cost += r.cost_usd
        if not r.error:
            agg.setdefault(lab, []).append([r.noul(q) for q in Q] + [len(s["email"].split())])
    jev.append_ledger({"caller": "prodcraft_campaign.build_copy_gtm", "items": len(states), "cost_usd": cost})
    print(f"{'niche':<9}{'template':<26}" + "".join(f"{q:>8}" for q in Q) + "  words  verdict")
    for lab, v in agg.items():
        lo = {q: min(x[i] for x in v) for i, q in enumerate(Q)}
        lo["slop"] = max(x[1] for x in v)
        gate = GATE if lab[1].startswith("step1") else {k: t for k, t in GATE.items() if k not in ("pain", "fit")}
        ok = all(lo[q] >= t for q, t in gate.items()) and lo["slop"] <= 0.60
        print(f"{lab[0]:<9}{lab[1]:<26}" + "".join(f"{lo[q]:8.2f}" for q in Q)
              + f"  {min(x[-1] for x in v)}-{max(x[-1] for x in v)}  {'PASS' if ok else 'FAIL'}")
    out["approved"] = a.approved
    (HERE / "copy_gtm.json").write_text(json.dumps(out, indent=1))
    print(f"jev ${cost:.4f}; wrote copy_gtm.json (approved={a.approved})")


if __name__ == "__main__":
    main()
