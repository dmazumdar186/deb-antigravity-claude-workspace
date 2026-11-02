"""
description: Build the ProdCraft Proposal Engine copy sets (Instantly spintax) and gate them with Jev.inputs: none (copy is defined in code); env OPENROUTER key for Jev
outputs: copy.json next to this script; stdout Jev human/slop scores per template
"""
import json, random, re, sys
from pathlib import Path
ROOT = Path('/home/user/deb-antigravity-claude-workspace'); sys.path.insert(0, str(ROOT))
from execution.modules import jev_client as jev

NICHES = {
 "EventAV":  dict(item="pitch deck", short="deck", win="pitches", nxt="pitch"),
 "FitoutUS": dict(item="bid proposal", short="proposal", win="bids", nxt="bid"),
 "FitoutUK": dict(item="tender submission", short="tender", win="tenders", nxt="tender"),
 "DMC":      dict(item="program proposal", short="proposal", win="programs", nxt="RFP"),
}
OPEN = ("{{RANDOM | hi | hey}} {{firstName}}, {{RANDOM | i think i'm an introvert | i'd call myself an introvert}}, "
        "{{RANDOM | but my close friends say | though my close friends say}} i talk too much, so "
        "{{RANDOM | i'll keep this short | i'll keep this brief | i'll make this quick}}.")
PERS = " {{RANDOM | saw {{project_reference}} on your site. | was looking at {{project_reference}} on your site.}}"
def build(n):
    p = NICHES[n]
    body = ("\n\n{{RANDOM | i just rebuilt | i recently rebuilt}} 6 companies' websites as live concept sites from their own photos and words, "
            "{{RANDOM | 48 hours each | each in 48 hours}}.\n\n"
            f"{{{{RANDOM | send me one past {p['item']} | send over one old {p['item']}}}}} and i'll rebuild it as a live link in 72 hours. "
            "you'll {{RANDOM | know | see}} the moment your client opens it.\n\n"
            "{{RANDOM | interested? | sound interesting? | worth a look?}}\n\n"
            f"ps. {{{{RANDOM | it's free | the first one's on me}}}}. a lost {p['short']} works fine too.")
    s2 = ("{{RANDOM | hi | hey}} {{firstName}}, just bumping this. {{RANDOM | forgot to mention | one more thing}}, "
          "i've shipped 12+ AI tools for clients this year, and my own proposals go out the same way, so it's not theory.\n\n"
          "{{RANDOM | if timing's bad | if the timing's off}}, no worries. {{RANDOM | but if there's any interest | if there's any interest though}}, "
          f"send one old {p['short']} over and you'll have it back as a live link in 3 days.")
    s3 = ("{{RANDOM | hi | hey}} {{firstName}}, {{RANDOM | last one from me. | last email from me. | last note from me.}} "
          f"the setup's built, {{{{RANDOM | just need one of your old {p['short']}s | only thing missing is one of your old {p['short']}s}}}}.\n\n"
          "{{RANDOM | as i said | like i mentioned}}, it's free. {{RANDOM | no worries if it's not the right time, just keep me in mind for when it is. "
          "| if the timing's off, no worries, just keep me in mind for down the line.}}")
    subj = ["{{firstName}} - partnership request for {{companyName}}",
            "{{RANDOM | open for collaborating {{firstName}} | open to collaborating {{firstName}}? | {{firstName}}, open to collaborating?}}",
            f"{{{{RANDOM | more {p['win']} won for {{{{companyName}}}} | ideas for {{{{firstName}}}}'s next {p['nxt']}}}}}"]
    return {"subjects": subj, "step1_personalized": OPEN + PERS + body, "step1_nopersonalization": OPEN + body, "step2": s2, "step3": s3}

SPIN = re.compile(r"\{\{RANDOM \|((?:[^{}]|\{\{[a-zA-Z_]+\}\})*)\}\}")
def render(t, v, rng):
    while True:
        m = SPIN.search(t)
        if not m: break
        t = t[:m.start()] + rng.choice([o.strip() for o in m.group(1).split('|')]) + t[m.end():]
    for k, val in v.items(): t = t.replace("{{%s}}" % k, val)
    assert "{{" not in t, t
    return t
SAMPLE = {"firstName": "Sarah", "companyName": "Northlight Productions", "project_reference": "the Kraken ScreamFest launch"}
Q = {"human": jev.noul("Does this cold email read like one real person typed it quickly by hand?",
        "true when casual, plain, specific, lowercase-ish, no polished marketing phrasing",
        "false when it reads AI-written: polished, generic, 'most X I talk to', 'I came across', 'leverage', 'streamline', buzzwords"),
     "slop": jev.noul("Does this email contain generic AI-written sales cliches or filler?",
        "true when it has stock phrases like 'most teams I talk to', 'I hope this finds you well', 'game-changer', flattery",
        "false when every sentence is concrete and plain")}
BASELINE = ("Hi Sarah,\n\nSaw the 40,000 sf buildout in River North on your projects page.\n\nQuick question: how long does it take your team "
            "to go from a finished takeoff to a client-ready proposal? Most interior GCs I talk to have the takeoff fast and the proposal slow. "
            "I build AI pipelines that turn Bluebeam/Togal exports into branded proposals in hours, not days.\n\nWorth a look?\n\nDebanjan, ProdCraft")
if __name__ == "__main__":
    copy = {n: build(n) for n in NICHES}
    (Path(__file__).with_name('copy.json')).write_text(json.dumps(copy, indent=1))
    rng = random.Random(7); states, labels = [], []
    for n, c in copy.items():
        for key in ("step1_personalized", "step1_nopersonalization", "step2", "step3"):
            for i in range(4):
                states.append({"email": render(c[key], SAMPLE, rng)}); labels.append((n, key))
    states.append({"email": BASELINE}); labels.append(("baseline", "playbook_sec7"))
    rs = jev.decide_many(states, Q, workers=8)
    agg = {}
    for (n, k), r, s in zip(labels, rs, states):
        if r.error: print("ERR", n, k, r.error); continue
        agg.setdefault((n, k), []).append((r.noul("human"), r.noul("slop"), len(s["email"].split())))
    for (n, k), v in agg.items():
        print(f"{n:<9}{k:<26} human {min(x[0] for x in v):.2f}-{max(x[0] for x in v):.2f}  slop {max(x[1] for x in v):.2f}  words {min(x[2] for x in v)}-{max(x[2] for x in v)}")
