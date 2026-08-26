"""
instantly_bounce_analysis -- measure how much of a campaign's bounce problem an
MX pre-screen can actually solve, and project the post-cleanup bounce rate.

purpose: instantly_guard.py deletes leads on structurally dead domains. That
         catches only SOME bounces -- the rest are mailbox-level rejections on
         domains with perfectly valid MX. This script MEASURES the split so the
         operator knows whether DNS screening is a fix or a rounding error
         before deciding to resume a campaign.

         Written because the "3 of 13" and "~11.3% projected" figures were
         originally computed off-artifact in a throwaway shell. A claim stated
         as measured needs a surviving, re-runnable measurement.

inputs:  CLI: --leads PATH (a leads_raw.json snapshot from instantly_guard's
              population, i.e. a JSON list of Instantly lead objects)
              --contacted N (leads contacted at the time the bounces were
              observed; get it from FILTER_VAL_CONTACTED)
              --out PATH (JSON artifact, default alongside --leads)
              --resolver {auto,doh}

outputs: JSON artifact + a human table on stdout. Exit 0 always (measurement,
         not a gate).

notes:   Screens the BOUNCED domains -- the opposite population from the guard,
         which screens not-yet-contacted leads. That is the whole point: it asks
         "would the screen have caught the failures we already know about?"
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from instantly_guard import DEAD_VERDICTS, MxScreen, domain_of  # noqa: E402


def analyse(leads: list[dict], contacted: int, resolver: str) -> dict:
    bounced = [lead for lead in leads if lead.get("status") == -1]
    bounced_domains: dict[str, int] = collections.Counter()
    for lead in bounced:
        domain = domain_of(lead.get("email", ""))
        if domain:
            bounced_domains[domain] += 1

    screen = MxScreen(10.0, resolver)
    verdicts = screen.screen(sorted(bounced_domains), workers=10)

    catchable_domains = [d for d, (v, _) in verdicts.items() if v in DEAD_VERDICTS]
    catchable_leads = sum(bounced_domains[d] for d in catchable_domains)
    errored = [d for d, (v, _) in verdicts.items() if v.startswith("ERROR")]

    total_bounced = len(bounced)
    observed_rate = total_bounced / contacted if contacted else 0.0
    # Component of the bounce rate an MX screen can remove.
    catchable_rate = catchable_leads / contacted if contacted else 0.0
    # What is left after a perfect MX screen: mailbox-level failures on live MX.
    residual_rate = observed_rate - catchable_rate

    uncontacted = sum(1 for lead in leads
                      if lead.get("status") != -1 and lead.get("id")) - (contacted - total_bounced)
    uncontacted = max(uncontacted, 0)
    projected_new = uncontacted * residual_rate
    denom = contacted + uncontacted
    projected_rate = (total_bounced + projected_new) / denom if denom else 0.0

    return {
        "resolver_backend": screen.backend,
        "contacted": contacted,
        "bounced_leads": total_bounced,
        "bounced_domains": len(bounced_domains),
        "observed_bounce_rate": round(observed_rate, 4),
        "mx_verdicts": {d: verdicts[d][0] for d in sorted(verdicts)},
        "domains_mx_screen_would_catch": sorted(catchable_domains),
        "bounces_mx_screen_would_catch": catchable_leads,
        "bounces_mx_screen_would_miss": total_bounced - catchable_leads,
        "resolver_errors": errored,
        "catchable_rate": round(catchable_rate, 4),
        "residual_mailbox_level_rate": round(residual_rate, 4),
        "uncontacted_leads": uncontacted,
        "projected_new_bounces": round(projected_new, 1),
        "projected_campaign_bounce_rate": round(projected_rate, 4),
        "model": ("projected = (observed_bounces + uncontacted * residual_rate) "
                  "/ (contacted + uncontacted); residual_rate = the share of "
                  "observed bounces an MX screen CANNOT catch. Assumes the "
                  "uncontacted population behaves like the contacted one."),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--leads", type=Path, required=True)
    parser.add_argument("--contacted", type=int, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--resolver", choices=("auto", "doh"), default="auto")
    args = parser.parse_args()

    leads = json.loads(args.leads.read_text(encoding="utf-8"))
    result = analyse(leads, args.contacted, args.resolver)

    out = args.out or args.leads.with_name("bounce_analysis.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"resolver backend            {result['resolver_backend']}")
    print(f"contacted                   {result['contacted']}")
    print(f"bounced                     {result['bounced_leads']} "
          f"across {result['bounced_domains']} domains")
    print(f"observed bounce rate        {result['observed_bounce_rate']:.1%}")
    print()
    print(f"{'BOUNCED DOMAIN':<28} MX VERDICT")
    print("-" * 44)
    for domain, verdict in result["mx_verdicts"].items():
        mark = "  <- catchable" if verdict in DEAD_VERDICTS else ""
        print(f"{domain:<28} {verdict}{mark}")
    print("-" * 44)
    print()
    print(f"an MX screen would have caught   "
          f"{result['bounces_mx_screen_would_catch']} of {result['bounced_leads']} bounces")
    print(f"it would have MISSED             "
          f"{result['bounces_mx_screen_would_miss']} (valid MX, dead mailbox)")
    print(f"catchable component of rate      {result['catchable_rate']:.1%}")
    print(f"residual mailbox-level rate      {result['residual_mailbox_level_rate']:.1%}")
    print()
    print(f"uncontacted leads                {result['uncontacted_leads']}")
    print(f"projected new bounces            ~{result['projected_new_bounces']}")
    print(f"PROJECTED CAMPAIGN BOUNCE RATE   {result['projected_campaign_bounce_rate']:.1%}")
    if result["resolver_errors"]:
        print(f"\nWARNING: {len(result['resolver_errors'])} domains had resolver errors "
              f"and are excluded from the catchable count: {result['resolver_errors']}")
    print(f"\nartifact -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
