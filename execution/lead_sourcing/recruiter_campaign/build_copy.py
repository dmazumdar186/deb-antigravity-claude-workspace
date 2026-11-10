"""Recruiter (Candidate Outreach System) copy: two angles, spintax on every line, Jev humanizer gate.

description: Builds the DM_Recruitment copy variants (A result-led, B mechanism-led), renders each spin many ways and
             scores every render with Jev (human, slop, pain, fit, plain, prospect); writes copy.json for the chosen angle.
inputs: --angle A|B (which angle to write to copy.json; default: none, scores only); --renders N; env OPENROUTER_API_KEY
outputs: stdout score table (min human / max slop etc. per template); copy.json next to this script when --angle set;
         .tmp/jev_ledger.jsonl row
usage:
    python3 execution/lead_sourcing/recruiter_campaign/build_copy.py               # score both angles
    python3 execution/lead_sourcing/recruiter_campaign/build_copy.py --angle A     # also write copy.json
Directive: directives/lead_sourcing/recruiter_campaign.md

Sources for every claim (grounding):
- A: operator's own Oct 2026 DM_Recruitment copy (Instantly, read 2026-11-10): Dublin agency, June 2026, ~15 hours a
  week back per consultant, candidate replies 2.3x; offer of screened candidates on one live role.
- B: the operator's Loom summary (loom.com/share/0e16c5a3f6ab4cf099fe4d7f4ede0aef): built for senior structural
  engineer recruiting; checks candidates against LinkedIn and public experience; writes the LinkedIn note, email and
  a follow-up a week later; brings back people already contacted.
- Offer (operator 2026-11-10, "keep the offer"): set it up on one open role. Link only in step 2 (operator).
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
from execution.modules import jev_client as jev  # noqa: E402

LOOM = "https://www.loom.com/share/0e16c5a3f6ab4cf099fe4d7f4ede0aef"  # old link (shows real candidate names; replaced)
VIDEO = "https://prodcraft.fyi/recruit"  # operator's 31 s video, demo data only, hosted on the ProdCraft site


def R(*opts: str) -> str:
    """One spintax line."""
    return "{{RANDOM|" + "|".join(opts) + "}}"


# H (hybrid, 2026-11-10 web research): step 1 = recruiter pain + result + free offer as an interest question;
# mechanism + Loom move to step 2. Subjects lowercase, 2-4 words, no numbers (30MPC/Gong: numbers cut opens).
SUBJECTS_H = [R("sourcing at {{companyName}}", "{{companyName}} sourcing", "{{firstName}}, sourcing?"),
              R("your open roles", "one of your roles", "quick question {{firstName}}")]
PAIN = R("bet sourcing still eats a big chunk of your week.",
         "my guess is finding candidates still takes most of your day.",
         "sourcing probably takes more of your week than you'd like.")
RESULT = [R("this june i built a tool for a recruiting agency in dublin.",
            "back in june i built something for an agency in dublin.",
            "in june i built a sourcing tool for a dublin recruiting agency."),
          R("their consultants got about 15 hours a week back and candidate replies went up 2.3x.",
            "each consultant got ~15 hours a week back, and replies from candidates went up 2.3x.",
            "each consultant there got roughly 15 hours a week back. candidate replies went up 2.3x.")]
OFFER_Q = R("want me to set it up on one of your open roles?",
            "should i set it up on one of your open roles?",
            "want me to try it on one of your open roles?")
STEP2_H = [R("{{firstName}}, here's a 30 second video of how it works:",
             "{{firstName}}, made a quick 30 second video of how it works:",
             "here's a 30 second video of how it works, {{firstName}}:"),
           R(VIDEO, f"{VIDEO} (30 sec)", f"video: {VIDEO}"),  # video 31.6 s
           R("it checks each candidate's linkedin and past work, then writes the first message and the follow-up.",
             "it looks up each candidate's linkedin and work history and drafts the message and the follow-up.",
             "it checks candidates against their linkedin, then writes the note and the follow-up for you."),
           R("so you spend a lot less time digging for candidates.",
             "means a lot less time hunting for candidates.",
             "so you spend way less time searching."),
           R("load your past candidates and they come back up with the next note ready.",
             "give it your old contact list and each one pops back up with a new message written.",
             "past candidates you load come back up too, with the next note already written."),
           R("worth a look?", "worth 3 minutes?", "want me to set it up on one of your roles?")]
STEP3_H = [R("last one {{firstName}}.", "last note from me {{firstName}}.", "{{firstName}}, last one."),
           R("if sourcing isn't a pain at {{companyName}} right now, just say so and i'll stop.",
             "if finding candidates isn't a headache at {{companyName}} right now, lmk and i'll stop.",
             "if this isn't a priority at {{companyName}}, tell me and i'll leave you alone."),
           R("if it is, send me one open role and the first 13 candidates are free.",
             "if it is, reply with one role and i'll send the first 13 candidates free.",
             "if it is, send one open role and the first list of 13 candidates is on me.")]

SUBJECTS = {
    "A": [R("{{companyName}} sourcing", "sourcing at {{companyName}}", "{{firstName}}, sourcing?"),
          R("15 hours back?", "hours back on sourcing", "quick one {{firstName}}")],
    "B": [R("{{companyName}} outreach", "outreach at {{companyName}}", "{{firstName}}, outreach?"),
          R("your first messages", "candidate messages", "quick one {{firstName}}")],
}
GREET = R("hey {{firstName}},", "hi {{firstName}},", "{{firstName}},")
PERS = R("saw you're doing {{specialty}} at {{companyName}}.", "saw you handle {{specialty}} at {{companyName}}.",
         "you're doing {{specialty}} at {{companyName}}, right?")
NOPERS = R("quick one, i'll keep it short.", "i'll keep this short.", "short one, promise.")
OFFER = R("happy to set it up on one of your open roles so you see it on your own pipeline.",
          "if you want, i'll set it up on one open role so you see it with real candidates.",
          "i can set it up on one open role you've got, so you see it on your own pipeline.")
ASK1 = R("worth a look?", "want me to?", "open to it?")

BODY = {
    "A": [R("back in june i built something for a recruiting agency in dublin.",
            "in june i built a sourcing setup for a dublin recruiting agency.",
            "this june i built a sourcing tool for an agency in dublin."),
          R("each consultant got about 15 hours a week back, and candidates replied 2.3x more.",
            "their consultants got ~15 hours a week back and candidate replies went up 2.3x.",
            "every consultant there got roughly 15 hours a week back. replies from candidates went up 2.3x.")],
    "B": [R("i built a tool for a team hiring senior structural engineers.",
            "i built something for a recruiting team hiring senior structural engineers.",
            "a team hiring senior structural engineers asked me to fix their outreach, so i built a tool."),
          R("it checks each candidate's linkedin and work history, then writes the first message and the follow-up.",
            "it looks up each candidate's linkedin and past work, then drafts the message and the follow-up a week later.",
            "it checks candidates against their linkedin, then writes the note and the follow-up for them."),
          R("it even brings back people they messaged before, with the next note ready.",
            "people they'd already messaged come back up with a new note ready.",
            "anyone they contacted before pops back up with the next message written.")],
}
STEP2 = [R("{{firstName}}, here's a short video of it in case that's easier than a reply:",
           "{{firstName}}, recorded a quick video of it, in case that's easier:",
           "here's a 3 min loom of it {{firstName}}, if that's easier than replying:"),
         R(LOOM, f"{LOOM} (3 min)", f"video: {LOOM}"),
         R("the whole point is time back for your recruiters, less writing messages and more time on calls.",
           "it's all about giving your recruiters time back, less typing and more calls with candidates.",
           "the idea is your recruiters spend less time writing messages and more time on calls."),
         OFFER,
         R("want me to?", "should i?", "worth trying on one role?")]
STEP3 = [R("last one {{firstName}}.", "last note from me {{firstName}}.", "{{firstName}}, last one."),
         R("if outreach isn't a pain at {{companyName}} right now, just say so and i'll stop.",
           "if candidate outreach isn't a headache at {{companyName}} right now, lmk and i'll stop.",
           "if this isn't a priority at {{companyName}}, tell me and i'll leave you alone."),
         R("if it is, reply with one role and i'll set it up.", "if it is, send me one role and i'll set it up.",
           "otherwise just send one open role and i'll do the rest.")]


# Personalized hook + pain in one line (a separate pain line pushed step 1 past ~70 words and up the slop score).
PERS_PAIN = R("saw you do {{specialty}} at {{companyName}}, so i'm guessing sourcing eats a big chunk of your week.",
              "you handle {{specialty}} at {{companyName}}, so finding candidates probably eats most of your day.",
              "saw you're on {{specialty}} at {{companyName}}. sourcing probably takes more of your week than you'd like.")
# Operator 2026-11-10: make clear the first candidate list is free (no time or money asked before proof).
FREE = R("first list of 13 candidates is free, no call needed.",
         "the first 13 candidates are on me, no call needed.",
         "first list of 13 candidates is free. no call needed.")


def step1(angle: str, personalized: bool) -> str:
    if angle == "H":
        return "\n\n".join([GREET, PERS_PAIN if personalized else PAIN] + RESULT + [OFFER_Q, FREE])
    return "\n\n".join([GREET, PERS if personalized else NOPERS] + BODY[angle] + [OFFER, ASK1])


def copy_for(angle: str) -> dict:
    if angle == "H":
        return {"angle": "H", "subjects": SUBJECTS_H, "step1_personalized": step1("H", True),
                "step1_nopersonalization": step1("H", False), "step2": "\n\n".join(STEP2_H),
                "step3": "\n\n".join(STEP3_H)}
    return {"angle": angle, "subjects": SUBJECTS[angle], "step1_personalized": step1(angle, True),
            "step1_nopersonalization": step1(angle, False), "step2": "\n\n".join(STEP2), "step3": "\n\n".join(STEP3)}


SPIN = re.compile(r"\{\{RANDOM\|((?:[^{}]|\{\{[a-zA-Z_]+\}\})*)\}\}")


def render(t: str, v: dict, rng: random.Random) -> str:
    while (m := SPIN.search(t)):
        t = t[:m.start()] + rng.choice(m.group(1).split("|")) + t[m.end():]
    for k, val in v.items():
        t = t.replace("{{%s}}" % k, val)
    if "{{" in t:
        raise ValueError(f"unrendered placeholder: {t[:200]}")
    return t


def lint(c: dict) -> list[str]:
    """Every non-link line of every step and every subject must carry spintax (operator 2026-11-10)."""
    bad = []
    for key in ("step1_personalized", "step1_nopersonalization", "step2", "step3"):
        for line in c[key].split("\n\n"):
            if "{{RANDOM|" not in line:
                bad.append(f"{key}: {line[:60]}")
    bad += [f"subject: {s}" for s in c["subjects"] if "{{RANDOM|" not in s]
    return bad


Q = {"human": jev.noul("Does this cold email read like one real person typed it quickly by hand?",
                       "true when casual, plain, specific",
                       "false when polished, generic or AI-written ('most X I talk to', 'leverage', 'streamline')"),
     "slop": jev.noul("Does this email contain generic AI-written sales cliches or filler?",
                      "true when stock phrases or flattery", "false when every sentence is concrete"),
     "pain": jev.noul("Does the email name a concrete, specific problem this buyer (a recruiter) has in their own work?",
                      "true when it names a specific task the buyer struggles with (sourcing, writing outreach, follow-ups)",
                      "false when it only describes the sender or a generic offer"),
     "fit": jev.noul("Does every proof or offer line directly support solving that recruiter's problem?",
                     "true when the offer and proof are about the buyer's problem", "false when a line is unrelated"),
     "plain": jev.noul("Would a recruiter understand every sentence without software or tech jargon? Recruiting words "
                       "(sourcing, candidates, roles, pipeline, outreach) count as plain.",
                       "true when plain words a recruiter uses",
                       "false when it uses terms like AI pipeline, workflow automation, API, enrichment, LLM"),
     "prospect": jev.noul("Is the email mostly about the reader and their work rather than about the sender?",
                          "true when most sentences are about the reader", "false when most are about the sender")}
GATE = {"human": 0.70, "pain": 0.55, "fit": 0.55, "plain": 0.70}  # min over renders; slop max <= 0.60 (2 Nov calibration)
SAMPLE = {"firstName": "Sarah", "companyName": "Brightpath Staffing", "specialty": "healthcare hiring"}


def main() -> None:
    ap = argparse.ArgumentParser(description="Build + Jev-gate DM_Recruitment copy")
    ap.add_argument("--angle", choices=["A", "B", "H"], help="write copy.json for this angle")
    ap.add_argument("--renders", type=int, default=6)
    ap.add_argument("--approved", action="store_true", help="mark copy.json operator-approved (only on the operator's word)")
    a = ap.parse_args()
    rng = random.Random(7)
    states, labels = [], []
    for angle in ("A", "B", "H"):
        c = copy_for(angle)
        if (bad := lint(c)):
            sys.exit(f"spintax lint failed for {angle}: {bad}")
        for key in ("step1_personalized", "step1_nopersonalization", "step2", "step3"):
            for _ in range(a.renders):
                subj = render(rng.choice(c["subjects"]), SAMPLE, rng) if key.startswith("step1") else ""
                states.append({"subject": subj, "email": render(c[key], SAMPLE, rng)})
                labels.append((angle, key))
    rs = jev.decide_many(states, Q, workers=8)
    cost, agg = 0.0, {}
    for lab, r, s in zip(labels, rs, states):
        cost += r.cost_usd
        if r.error:
            print("ERR", lab, r.error)
            continue
        agg.setdefault(lab, []).append([r.noul(q) for q in Q] + [len(s["email"].split())])
    jev.append_ledger({"caller": "recruiter_campaign.build_copy", "items": len(states), "cost_usd": cost})
    print(f"{'angle':<6}{'template':<26}" + "".join(f"{q:>9}" for q in Q) + "  words  verdict")
    for lab, v in agg.items():
        lo = {q: min(x[i] for x in v) for i, q in enumerate(Q)}
        lo["slop"] = max(x[1] for x in v)
        # pain/fit apply to step 1 (the sell); follow-ups and the breakup gate on human, slop and plain only.
        gate = GATE if lab[1].startswith("step1") else {k: v for k, v in GATE.items() if k not in ("pain", "fit")}
        ok = all(lo[q] >= t for q, t in gate.items()) and lo["slop"] <= 0.60
        words = f"{min(x[-1] for x in v)}-{max(x[-1] for x in v)}"
        print(f"{lab[0]:<6}{lab[1]:<26}" + "".join(f"{lo[q]:9.2f}" for q in Q) + f"  {words:>6}  {'PASS' if ok else 'FAIL'}")
    print(f"jev cost ${cost:.4f}")
    if a.angle:
        c = copy_for(a.angle)
        c["approved"] = a.approved  # launch.py refuses --apply until the operator has approved the copy
        (HERE / "copy.json").write_text(json.dumps(c, indent=1))
        print(f"wrote copy.json (angle {a.angle})")


if __name__ == "__main__":
    main()
