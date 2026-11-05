"""ProdCraft Proposal Engine copy v2: pain-led, Siva-structured, Jev-gated.

description: Builds v2 copy (per niche x country) from the playbook pain points and Siva's winning structure, then gates it with Jev.
inputs: env OpenRouter key (Jev); copy.json (v1) for the baseline comparison
outputs: copy_v2.json next to this script; stdout Jev scores per template incl. v1 and playbook baselines
"""
import json, random, re, sys
from pathlib import Path
HERE = Path(__file__).parent; ROOT = HERE.parents[2]; sys.path.insert(0, str(ROOT))
from execution.modules import jev_client as jev

N = {  # pain + trigger from the playbook (sections 2A-2C), offer/guarantee from section 4
 "EventAV": dict(buyer="production companies", trigger="january kickoffs being pitched right now",
   pain="your team rebuilds a pitch deck from scratch for every brief",
   offer="a client brief becomes a first-draft deck the same day, built from your past decks",
   thing="deck", things="decks", unit="pitches", subj=["{{companyName}}'s next pitch deck", "pitch decks for 2027", "{{companyName}} rfp season?"]),
 "FitoutUS": dict(buyer="interior contractors", trigger="bid season picking up",
   pain="turning a finished estimate into a proposal still takes your team days",
   offer="your finished estimate turns into a ready-to-send proposal the same day",
   thing="bid", things="bids", unit="bids", subj=["{{companyName}}'s next bid", "bid proposals at {{companyName}}", "{{companyName}} bid season?"]),
 "FitoutUK": dict(buyer="fit-out contractors", trigger="tender season picking up",
   pain="turning a finished estimate into a tender still takes your team days",
   offer="your finished estimate turns into a ready-to-send tender the same day",
   thing="tender", things="tenders", unit="tenders", subj=["{{companyName}}'s next tender", "tender submissions at {{companyName}}", "{{companyName}} tender season?"]),
 "DMC": dict(buyer="incentive travel companies", trigger="2027 incentive trips being planned now",
   pain="your team builds every trip proposal by hand from hotel and supplier quotes",
   offer="the trip proposal is ready the same day the quotes come in",
   thing="proposal", things="proposals", unit="programs", subj=["{{companyName}}'s 2027 programs", "program proposals at {{companyName}}", "{{companyName}} incentive rfps?"]),
}
GREET = "{{RANDOM | hey {{firstName}}, | hi {{firstName}}, }}"
PERSONA = "my friends say i talk too much, so {{RANDOM | i'll keep this short | i'll keep this brief}}."
def step1(n, country, personalized, persona):
    p = N[n]; where = "the US" if country == "US" else "the UK"
    hook = "{{RANDOM | saw | noticed}} {{project_reference}} on your site." if personalized else f"with {p['trigger']}, i'm guessing {p['pain']}."
    lines = [GREET]
    if persona: lines.append(PERSONA)
    lines.append(hook)
    if personalized: lines.append(f"with {p['trigger']}, i'm guessing {p['pain']}.")
    lines += [f"i set things up so {p['offer']}. {{{{RANDOM | looking for | now looking for}}}} 2 {p['buyer']} in {where} to do this for.",
              "{{RANDOM | want me to send over an example? | should i send over an example? | want to see an example?}}",
              f"ps. if it doesn't halve your team's {p['thing']} time over the next 5 {p['unit']}, {{{{RANDOM | you get your money back | i refund you in full}}}}.",
              "pps. if you'd rather not hear from me, just lmk and i'll stop."]
    return "\n\n".join(lines)
def step2(n):
    p = N[n]
    return "\n\n".join([GREET, "{{RANDOM | one thing i didn't mention in my last email. | one thing i left out of my last email.}}",
        f"you don't change any software or learn anything new. you send me 10 of your past {p['things']}, i set everything up in about 2 weeks, and your part is maybe an hour.",
        f"after that, a new brief doesn't mean starting a {p['thing']} from a blank page.",
        "{{RANDOM | worth a 15-minute chat? | open to 15 minutes? | worth 15 minutes?}}"])
def step3(n):
    p = N[n]
    return "\n\n".join([GREET, "{{RANDOM | last one from me. | last email from me.}}",
        f"{p['offer']}. if it doesn't halve your team's {p['thing']} time over the next 5 {p['unit']}, {{{{RANDOM | you get your money back | i refund you in full}}}}.",
        "{{RANDOM | want me to send over an example? | should i send over an example?}}",
        "either way, {{RANDOM | rooting for | cheering for}} {{companyName}}."])
def build():
    out = {}
    for n in N:
        for country in (["US"] if n == "FitoutUS" else ["UK"] if n == "FitoutUK" else ["US", "UK"]):
            for pers in ("Personalized", "NoPersonalization"):
                pz = pers == "Personalized"
                out[f"{n}|{country}|{pers}"] = {"subjects": N[n]["subj"],
                    "step1_variants": {"A_prospect_first": step1(n, country, pz, False), "B_persona_opener": step1(n, country, pz, True)},
                    "step2": step2(n), "step3": step3(n)}
    return out

SPIN = re.compile(r"\{\{RANDOM \|((?:[^{}]|\{\{[a-zA-Z_]+\}\})*)\}\}")
def render(t, v, rng):
    while (m := SPIN.search(t)):
        t = t[:m.start()] + rng.choice([o.strip() for o in m.group(1).split('|')]) + t[m.end():]
    for k, val in v.items(): t = t.replace("{{%s}}" % k, val)
    if "{{" in t:
        raise ValueError(f"unrendered placeholder in outward copy: {t[:200]}")
    return t
Q = {"human": jev.noul("Does this cold email read like one real person typed it quickly by hand?",
        "true when casual, plain, specific", "false when polished, generic or AI-written ('most X I talk to', 'leverage', 'streamline')"),
     "slop": jev.noul("Does this email contain generic AI-written sales cliches or filler?", "true when stock phrases or flattery", "false when every sentence is concrete"),
     "pain": jev.noul("Does the email name a concrete, specific problem this buyer has in their own work?",
        "true when it names a specific task/deadline the buyer struggles with", "false when it only describes the sender or a generic offer"),
     "fit": jev.noul("Does every proof or offer line directly support solving that buyer's problem?",
        "true when the offer and proof are about the buyer's problem", "false when a line is about something unrelated (e.g. building websites for a proposal problem)"),
     "plain": jev.noul("Would a non-technical company owner understand every sentence without software or tech jargon? Everyday words of their own industry (deck, bid, tender, estimate, itinerary, DMC, incentive trip) count as plain.",
        "true when plain words a founder or director uses", "false when it uses technical terms like AI pipeline, RAG, workflow automation, API, system"),
     "prospect": jev.noul("Is the email mostly about the reader and their business rather than about the sender?",
        "true when most sentences are about the reader", "false when most sentences are about the sender")}
SAMPLE = {"firstName": "Sarah", "companyName": "Northlight Productions", "project_reference": "the Kraken ScreamFest launch"}
if __name__ == "__main__":
    copy = build(); (HERE/'copy_v2.json').write_text(json.dumps(copy, indent=1))
    v1 = json.loads((HERE/'copy.json').read_text())
    rng = random.Random(11); states, labels = [], []
    for k, c in copy.items():
        for var, t in list(c["step1_variants"].items()) + [("step2", c["step2"]), ("step3", c["step3"])]:
            for _ in range(3): states.append({"email": render(t, SAMPLE, rng)}); labels.append((k, var))
    for _ in range(3): states.append({"email": render(v1["EventAV"]["step1_personalized"], SAMPLE, rng)}); labels.append(("V1_LIVE|EventAV", "step1"))
    rs = jev.decide_many(states, Q, workers=8); agg = {}
    for lab, r, s in zip(labels, rs, states):
        if r.error: print("ERR", lab, r.error); continue
        agg.setdefault(lab, []).append([r.noul(q) for q in Q] + [len(s["email"].split())])
    print(f"{'template':<36}{'variant':<18}" + "".join(f"{q:>9}" for q in Q) + "    words")
    for lab, v in agg.items():
        mins = [min(x[i] for x in v) for i in range(len(Q))]; mx_slop = max(x[1] for x in v)
        mins[1] = mx_slop
        print(f"{lab[0]:<36}{lab[1]:<18}" + "".join(f"{m:9.2f}" for m in mins) + f"    {min(x[-1] for x in v)}-{max(x[-1] for x in v)}")
