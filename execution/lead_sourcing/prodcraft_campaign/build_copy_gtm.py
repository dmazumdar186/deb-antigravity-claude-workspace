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
- Offer (operator approval pending in this draft): first 50 people to contact (emails checked) free, no call needed.
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
                    buyer_q="companies that run conferences, launches and brand events"),
    "Fitout": dict(buyers="companies planning an office move or refit", work="fit-out work",
                   buyer_q="companies planning an office move, expansion or refit"),
    "DMC": dict(buyers="companies planning incentive trips and offsites", work="incentive and group trips",
                buyer_q="companies that run incentive trips, offsites and sales kick-offs"),
}
GREET = R("hey {{firstName}},", "hi {{firstName}},", "{{firstName}},")


def subjects(n: str) -> list[str]:
    return [R("new clients for {{companyName}}", "{{companyName}} pipeline", "{{firstName}}, new clients?"),
            R("your next client", "more corporate clients", "{{firstName}}, quick one")]


def pers(n: str) -> str:
    return R("saw {{project_reference}} on your site.", "noticed {{project_reference}} on your site.",
             "was reading about {{project_reference}} on your site.")


def pain(n: str) -> str:
    w = NICHE[n]["work"]
    return R(f"guessing most new {w} still comes from referrals and repeat clients?",
             f"my guess is new {w} still mostly comes through referrals.",
             f"bet most of your {w} still comes from people who already know you.")


PROOF = [R("this year i built something for a company that buys small businesses.",
           "earlier this year i built this for a company that buys small businesses.",
           "this year i set this up for a firm that buys small businesses."),
         R("they went from about a dozen emails a day, written by hand, to 800 a day.",
           "they went from roughly 12 emails a day by hand to 800 a day.",
           "about a dozen emails a day by hand turned into 800 a day.")]


def offer_q(n: str) -> str:
    b = NICHE[n]["buyers"]
    return R(f"want me to set it up for {{{{companyName}}}}, aimed at {b}?",
             f"should i build one for you, aimed at {b}?",
             f"want me to point it at {b} near you?")


FREE = R("the first 50 people to contact, emails checked, are free. no call needed.",
         "first 50 names with checked emails are on me, no call needed.",
         "first list of 50 people, emails checked, is free. no call needed.")


def step1(n: str, personalized: bool) -> str:
    lines = [GREET] + ([pers(n)] if personalized else []) + [pain(n)] + PROOF + [offer_q(n), FREE]
    return "\n\n".join(lines)


def step2(n: str) -> str:
    return "\n\n".join([
        R("{{firstName}}, here's a 30 second video of how it works:",
          "{{firstName}}, made a quick 30 second video of how it works:",
          "here's a 30 second video of how it works, {{firstName}}:"),
        R(VIDEO, f"{VIDEO} (30 sec)", f"video: {VIDEO}"),
        R("it finds the right people, checks each email address, then sends from lots of email accounts every day.",
          "it finds the right people, checks every email before sending and spreads the sending over many accounts.",
          "it finds the people, checks each email first, then sends a few from each of many accounts."),
        R("you only see the replies worth answering, and the best ones ping your phone.",
          "replies get sorted for you. when someone's keen, your phone pings and you take it from there.",
          "you get the good replies, and your phone pings when someone's ready to talk."),
        R("worth a look?", "worth 30 seconds?", "want me to set one up for you?")])


def step3(n: str) -> str:
    b = NICHE[n]["buyers"]
    return "\n\n".join([
        R("last one, {{firstName}}.", "last note from me, {{firstName}}.", "{{firstName}}, last one."),
        R("if new clients aren't a priority at {{companyName}} right now, say so and i'll stop.",
          "if winning new clients isn't on the list at {{companyName}} right now, tell me and i'll stop.",
          "if this isn't a priority for {{companyName}}, say so and i'll leave you alone."),
        R(f"if it is, reply yes and the first 50 people at {b} are free, emails checked.",
          f"if it is, a quick yes gets you the first 50 names at {b}, free.",
          f"if it is, reply yes and i'll send the first 50 names at {b}, free.")])


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
     "plain": jev.noul("Would a non-technical company owner understand every sentence without software jargon?",
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
