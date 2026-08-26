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
              --contacted N (fallback only; prefer --campaign-id, which pulls the
              real denominators from /campaigns/analytics)
              --campaign-id UUID (recommended: fetches emails_sent_count /
              bounced_count / contacted_count live)
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
from instantly_guard import (  # noqa: E402
    DEAD_VERDICTS, Instantly, MxScreen, domain_of, resolve_api_key,
)

# Instantly auto-pauses a campaign whose bounce rate exceeds this, once it has
# sent at least MIN_EMAILS_FOR_CHECK emails. Default 5%, customisable per
# workspace. Source: help.instantly.ai "High Bounce Auto-Pause Feature".
# CRITICAL: the denominator is EMAILS SENT, not leads contacted. Using
# contacted-leads inflates the rate by ~2x on a multi-step sequence and makes a
# recoverable campaign look hopeless.
BOUNCE_PROTECT_THRESHOLD = 0.05
MIN_EMAILS_FOR_CHECK = 200


def live_denominators(campaign_id: str, api_key_env: str, env_file) -> dict:
    """Pull the real counters Instantly measures against."""
    api = Instantly(resolve_api_key(api_key_env, env_file))
    payload = api.expect("GET", f"/campaigns/analytics?id={campaign_id}")
    row = payload[0] if isinstance(payload, list) else payload
    return {
        "emails_sent": row["emails_sent_count"],
        "contacted": row["contacted_count"],
        "bounced": row["bounced_count"],
        "leads": row["leads_count"],
    }


def analyse(leads: list[dict], contacted: int, resolver: str, live: dict | None = None) -> dict:
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

    # Count the uncontacted population DIRECTLY rather than deriving it by
    # subtraction. Subtraction mixes a live analytics `contacted` (which keeps
    # counting historical sends for leads since deleted) with a point-in-time
    # lead file, and silently drifts. A lead with no last-contact timestamp and
    # a non-bounced status has genuinely never been emailed.
    direct = [lead for lead in leads
              if lead.get("status") not in (-1, 3)
              and not lead.get("timestamp_last_contact")]
    if direct:
        uncontacted = len(direct)
    else:  # older snapshots may lack the timestamp field -- fall back
        uncontacted = max(
            sum(1 for lead in leads if lead.get("status") != -1 and lead.get("id"))
            - (contacted - total_bounced), 0)
    projected_new = uncontacted * residual_rate
    denom = contacted + uncontacted
    projected_rate = (total_bounced + projected_new) / denom if denom else 0.0

    # --- the denominator Instantly actually uses -------------------------
    sent = (live or {}).get("emails_sent")
    emails_per_lead = (sent / contacted) if (sent and contacted) else None
    rate_on_sent = (total_bounced / sent) if sent else None
    if sent and emails_per_lead:
        projected_sent_total = sent + uncontacted * emails_per_lead
        projected_rate_on_sent = (total_bounced + projected_new) / projected_sent_total
        # A verification pass that catches ~90% of dead mailboxes.
        verified_new = projected_new * 0.10
        verified_rate_on_sent = (total_bounced + verified_new) / projected_sent_total
    else:
        projected_rate_on_sent = verified_rate_on_sent = None

    return {
        "resolver_backend": screen.backend,
        "bounce_protect_threshold": BOUNCE_PROTECT_THRESHOLD,
        "min_emails_before_check": MIN_EMAILS_FOR_CHECK,
        "emails_sent": sent,
        "emails_per_contacted_lead": round(emails_per_lead, 2) if emails_per_lead else None,
        "observed_rate_on_emails_sent": round(rate_on_sent, 4) if rate_on_sent else None,
        "projected_rate_on_emails_sent_as_is": (
            round(projected_rate_on_sent, 4) if projected_rate_on_sent else None),
        "projected_rate_on_emails_sent_after_verification": (
            round(verified_rate_on_sent, 4) if verified_rate_on_sent else None),
        "clears_threshold_as_is": (
            projected_rate_on_sent < BOUNCE_PROTECT_THRESHOLD
            if projected_rate_on_sent else None),
        "clears_threshold_after_verification": (
            verified_rate_on_sent < BOUNCE_PROTECT_THRESHOLD
            if verified_rate_on_sent else None),
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
    parser.add_argument("--contacted", type=int,
                        help="fallback if --campaign-id is not given")
    parser.add_argument("--campaign-id",
                        help="pull live emails_sent / bounced / contacted from "
                             "/campaigns/analytics -- strongly preferred, since "
                             "Instantly measures against EMAILS SENT")
    parser.add_argument("--api-key-env", default="INSTANTLY_NOTIFIER_API_KEY")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--resolver", choices=("auto", "doh"), default="auto")
    args = parser.parse_args()

    live = None
    if args.campaign_id:
        live = live_denominators(args.campaign_id, args.api_key_env, args.env_file)
        contacted = live["contacted"]
    elif args.contacted:
        contacted = args.contacted
    else:
        parser.error("give --campaign-id (preferred) or --contacted")

    leads = json.loads(args.leads.read_text(encoding="utf-8"))
    result = analyse(leads, contacted, args.resolver, live)

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

    if result.get("emails_sent"):
        thr = result["bounce_protect_threshold"]
        print()
        print("=" * 62)
        print("CAN THIS CAMPAIGN BE RESUMED?")
        print("=" * 62)
        print(f"Instantly auto-pauses above {thr:.0%} of EMAILS SENT, once the")
        print(f"campaign has sent at least {result['min_emails_before_check']} emails.")
        print(f"Emails sent so far: {result['emails_sent']} "
              f"({result['emails_per_contacted_lead']} per contacted lead)")
        print()
        print(f"{'':<44}{'RATE':>8}  VERDICT")
        print("-" * 62)
        rows = [
            ("now (why it paused)", result["observed_rate_on_emails_sent"], None),
            ("resume as-is", result["projected_rate_on_emails_sent_as_is"],
             result["clears_threshold_as_is"]),
            ("resume after verifying the remaining leads",
             result["projected_rate_on_emails_sent_after_verification"],
             result["clears_threshold_after_verification"]),
        ]
        for label, rate, clears in rows:
            if rate is None:
                continue
            verdict = "" if clears is None else ("CLEARS" if clears else "RE-TRIPS")
            print(f"{label:<44}{rate:>8.2%}  {verdict}")
        print("-" * 62)
        # NOTE: a contacted-lead denominator roughly doubles these numbers on a
        # multi-step sequence and is NOT what Instantly measures. Kept below for
        # reference only.
        print(f"(for reference, on a contacted-lead denominator: "
              f"{result['projected_campaign_bounce_rate']:.1%} -- not the metric "
              f"Instantly gates on)")
    if result["resolver_errors"]:
        print(f"\nWARNING: {len(result['resolver_errors'])} domains had resolver errors "
              f"and are excluded from the catchable count: {result['resolver_errors']}")
    print(f"\nartifact -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
