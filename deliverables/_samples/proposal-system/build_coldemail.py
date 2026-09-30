#!/usr/bin/env python3
"""
Standard cold email proposal builder.

One template (template_coldemail.html) + one shared tool price table
(tool_costs.json) + a per-client config (clients/<slug>.json).

    python3 build_coldemail.py clients/acme.json
    npx vercel deploy --prod --yes

The pricing page, commission examples and agreement paragraph are GENERATED
from `pricing.model`, so a new client never means hand-rewriting legal text:

    commission_only            -> % of each closed deal, no retainer
    retainer_plus_commission   -> monthly retainer + %

Standing terms (billing on signature date, upfront, 30 days' notice, no
refunds, commission on deal signature, tool costs +3%) live in the template
and in STANDARD_TERMS.md. Do not restate them
per client.
"""
import json
import re
import secrets
import string
import sys
from datetime import date
from pathlib import Path

from build import base_url, fill  # reuse shared placeholder logic

SCRIPT_DIR = Path(__file__).parent
TEMPLATE_PATH = SCRIPT_DIR / "template_coldemail.html"
TOOL_COSTS_PATH = SCRIPT_DIR / "tool_costs.json"
PUBLIC_DIR = SCRIPT_DIR / "public"

CONVERSION_MARKUP = 1.03  # billed at cost +3% (currency conversion + processing)


REQUIRED = {
    "client": ["name", "title", "company"],
    "sender": ["name", "title", "company", "email"],
    "project": ["title", "cover_subtitle"],
    "pricing": ["model", "commission_pct"],
    "content": ["problems", "system_steps", "targets", "timeline",
                "next_steps", "funnel", "included_list"],
}


def validate(cfg, config_path):
    """Fail with a readable message naming the missing field, not a raw KeyError.

    These configs are edited by hand for every client, so a typo must say what to
    fix rather than dumping a traceback.
    """
    missing = []
    for section, fields in REQUIRED.items():
        if section not in cfg or cfg[section] is None:
            missing.append(section)
            continue
        missing += [f"{section}.{f}" for f in fields
                    if cfg[section].get(f) in (None, "")]
    if "linkedin_option" not in cfg:
        missing.append("linkedin_option")

    # Shape check: these render via render_list(), which needs a list of {title, body}.
    # A hand-edited config that makes one a string would otherwise fail deep in rendering.
    for field in ["problems", "system_steps", "timeline", "next_steps"]:
        items = cfg.get("content", {}).get(field)
        if items is not None and (
            not isinstance(items, list)
            or not all(isinstance(i, dict) and "title" in i and "body" in i for i in items)
        ):
            missing.append(f"content.{field} (must be a list of {{title, body}} objects)")

    if missing:
        raise SystemExit(
            f"{config_path}: missing required field(s):\n  "
            + "\n  ".join(missing)
            + "\n\nCompare against clients/_TEMPLATE.json."
        )


def base_mapping(cfg):
    """Client / sender / project placeholders.

    Deliberately not build.flatten(): that one also requires situation, scope and
    investment blocks, which this template dropped. Keeping it local means a client
    config holds only fields that actually render.
    """
    c, s, p = cfg["client"], cfg["sender"], cfg["project"]

    slug = c.get("company_slug")
    if not slug:
        base = c.get("company_slug_base") or re.sub(
            r"[^a-z0-9]+", "-", c["company"].lower()
        ).strip("-")
        suffix = "".join(
            secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6)
        )
        slug = f"{base}-{suffix}"  # unguessable even if the company name is known

    parts = s["company"].rsplit(" ", 1)
    wordmark = (
        f'{parts[0]} <span class="accent">{parts[1]}</span>'
        if len(parts) == 2 else s["company"]
    )

    stripe_url = cfg.get("payment", {}).get("stripe_url", "")

    return {
        # Client-supplied values are HTML-escaped for the document body and
        # JS-escaped separately for the inline <script> block.
        "CLIENT_NAME": esc_attr(c["name"]),
        "CLIENT_TITLE": esc_attr(c["title"]),
        "CLIENT_COMPANY": esc_attr(c["company"]),
        "CLIENT_COMPANY_JS": esc_js(c["company"]),
        "CLIENT_COMPANY_SLUG": slug,
        "STRIPE_PAYMENT_URL_JS": esc_js(stripe_url),
        "SENDER_NAME": s["name"],
        "SENDER_NAME_FIRST": s.get("name_first", s["name"].split()[0]),
        "SENDER_TITLE": s["title"],
        "SENDER_COMPANY": s["company"],
        "SENDER_COMPANY_WORDMARK": wordmark,
        "SENDER_EMAIL": s["email"],
        "SENDER_SIGNATURE_TEXT": s.get("signature_text", s["name"]),
        "LOGO_URL": s.get("logo_url", "/assets/logo.png"),
        "PROJECT_TITLE": p["title"],
        "COVER_BRAND_LABEL": p.get("cover_brand_label", "Lead Generation Proposal"),
        "COVER_SUBTITLE": p["cover_subtitle"],
        "CREATED_DATE": p.get("created_date") or date.today().isoformat(),
    }


def money(value):
    """2450.0 -> '2,450'   87.3 -> '87.30'   accepts "87.30" from a quoted JSON number."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"expected a number, got {value!r}")
    return f"{n:,.0f}" if n.is_integer() else f"{n:,.2f}"


def esc_attr(value):
    """Escape for an HTML attribute."""
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def esc_js(value):
    """Escape for embedding inside a double-quoted JS string literal.

    Client company/contact names land in inline <script> as string literals. An
    unescaped quote there breaks the whole block, which kills signature capture —
    i.e. the client cannot sign the contract.
    """
    # json.dumps handles quotes/backslashes/newlines but leaves "/" alone, so a
    # literal "</script>" would close the block early. Escape the slash too.
    return json.dumps(str(value))[1:-1].replace("/", "\\/")


def render_tool_rows(tool_costs, client_cfg):
    """Tools table rows + the monthly recurring subtotal (at cost, pre-markup)."""
    include = client_cfg.get("tools", {}).get("include")  # None = all
    overrides = client_cfg.get("tools", {}).get("overrides", {})

    # Read the Sales Nav price unconditionally: the LinkedIn risk clause quotes it
    # even when the tool is excluded from this client's table, and a stale hardcoded
    # figure there would be a wrong number inside a signed contract.
    salesnav = next((t for t in tool_costs["tools"] if t["id"] == "salesnav"), None)
    if salesnav:
        salesnav = {**salesnav, **overrides.get("salesnav", {})}
    salesnav_cost = money(salesnav["cost"]) if salesnav else None

    rows, monthly_total = [], 0.0
    for tool in tool_costs["tools"]:
        if include is not None and tool["id"] not in include:
            continue
        t = {**tool, **overrides.get(tool["id"], {})}

        name = f'<a href="{t["url"]}">{t["name"]}</a>' if t.get("url") else t["name"]
        if t.get("plan"):
            name += f' ({t["plan"]})'
        cost = f'{"~" if t.get("approx") else ""}${money(t["cost"])}/{t["period"]}'
        rows.append(
            f'      <tr><td>{name}</td><td>{t["purpose"]}</td>'
            f'<td class="amount">{cost}</td></tr>'
        )
        if t.get("recurring"):
            monthly_total += float(t["cost"])

    if salesnav_cost is None:
        raise ValueError(
            "tool_costs.json has no tool with id 'salesnav'. The LinkedIn risk clause "
            "quotes that price, so it must exist even if excluded from the client's table."
        )
    return "\n".join(rows), money(monthly_total), salesnav_cost


def render_pricing(pricing):
    """Pricing table rows, commission example tiles, and the agreement sentence.

    Returns (rows_html, examples_html, agreement_fee_sentence, commission_term).
    """
    model = pricing["model"]
    pct = pricing["commission_pct"]
    rows = []

    if model == "retainer_plus_commission":
        if pricing.get("retainer") is None:
            raise ValueError(
                "pricing.model is 'retainer_plus_commission' but pricing.retainer is not set. "
                "Set the monthly amount, or switch model to 'commission_only'."
            )
        if bool(pricing.get("retainer_raised")) != bool(pricing.get("retainer_raise_trigger")):
            raise ValueError(
                "pricing.retainer_raised and pricing.retainer_raise_trigger must be set together "
                "(a step-up amount needs the condition that triggers it, and vice versa)."
            )
        retainer = money(pricing["retainer"])
        covers = "Full done-for-you service, billed monthly."
        if pricing.get("retainer_raised"):
            covers += (
                f' Moves to ${money(pricing["retainer_raised"])}/mo '
                f'{pricing["retainer_raise_trigger"]}.'
            )
        rows.append(
            f'      <tr><td>Management fee</td><td>{covers}</td>'
            f'<td class="amount">${retainer}/mo</td></tr>'
        )
        fee_sentence = f"a ${retainer}/month management fee plus {pct}% on closed deals attributed to our outreach"
    elif model == "commission_only":
        rows.append(
            '      <tr><td>Management fee</td>'
            '<td>None. No retainer, no monthly minimum.</td>'
            '<td class="amount">$0</td></tr>'
        )
        fee_sentence = f"{pct}% on closed deals attributed to our outreach, with no retainer"
    else:
        raise ValueError(
            f"unknown pricing.model {model!r} "
            "(expected 'commission_only' or 'retainer_plus_commission')"
        )

    rows.append(
        f'      <tr><td>Commission</td>'
        f'<td>On each closed deal attributed to our outreach, invoiced when you sign the deal.</td>'
        f'<td class="amount">{pct}%</td></tr>'
    )
    rows.append(
        '      <tr><td>Lock-in</td>'
        "<td>None. Cancel any time with 30 days' notice.</td>"
        '<td class="amount">—</td></tr>'
    )

    examples = "\n".join(
        f'    <div class="item"><div class="num">DEAL SIZE</div>'
        f'<h4>${money(size)}</h4><p>Commission ({pct}%): '
        f'<strong style="color:var(--accent);">${money(size * pct / 100)}</strong></p></div>'
        for size in pricing.get("example_deal_sizes", [])
    )

    commission_term = (
        f"Commission ({pct}% of each closed deal) is invoiced when you sign the deal with your customer, "
        "not when they pay you."
    )
    return "\n".join(rows), examples, fee_sentence, commission_term


def render_linkedin(option, salesnav_cost):
    """The LinkedIn risk bullet. Their account = their risk; mine = they fund it."""
    if option == "client_account":
        body = (
            "Prospecting runs through LinkedIn Sales Navigator. Using your company account means "
            "there is a real, if uncommon, risk that LinkedIn restricts or bans it for automated "
            "activity. I keep usage conservative to minimise it, but I can't eliminate it, and by "
            "providing your account you're accepting that risk. If you'd rather not, I'll run "
            f"prospecting from my own account instead and you cover the seat (${salesnav_cost}/mo) "
            "— then the risk sits with me, not you."
        )
    elif option == "my_account":
        body = (
            "Prospecting runs through LinkedIn Sales Navigator on my account, funded by you at "
            f"${salesnav_cost}/mo. There is a real, if uncommon, risk that LinkedIn restricts an "
            "account for automated activity — running it on my side means that risk is mine to "
            "carry, not yours, and your company account is never exposed."
        )
    else:
        raise ValueError(
            f"unknown linkedin option {option!r} "
            "(expected 'client_account' or 'my_account')"
        )
    return f'    <li><strong>LinkedIn account risk</strong><span>{body}</span></li>'


def render_list(items, style):
    """style='problem' -> numbered grid tiles; 'scope' -> strong/span rows."""
    if style == "problem":
        return "\n".join(
            f'    <div class="item"><div class="num">{i:02d}</div>'
            f'<h4>{it["title"]}</h4><p>{it["body"]}</p></div>'
            for i, it in enumerate(items, 1)
        )
    return "\n".join(
        f'    <li><strong>{it["title"]}</strong><span>{it["body"]}</span></li>'
        for it in items
    )


def main():
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not config_path or not config_path.exists():
        sys.exit("usage: python3 build_coldemail.py clients/<slug>.json")

    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    validate(cfg, config_path)
    tool_costs = json.loads(TOOL_COSTS_PATH.read_text(encoding="utf-8"))

    mapping = base_mapping(cfg)
    mapping.update(cfg.get("extra", {}))

    tool_rows, tools_monthly, salesnav_cost = render_tool_rows(tool_costs, cfg)
    pricing_rows, examples, fee_sentence, commission_term = render_pricing(cfg["pricing"])

    content = cfg["content"]
    mapping.update({
        "PROBLEM_ITEMS": render_list(content["problems"], "problem"),
        "SYSTEM_STEPS": render_list(content["system_steps"], "scope"),
        "TARGETS_HEADING": content["targets"]["heading"],
        "TARGETS_SUBHEADING": content["targets"]["subheading"],
        "TARGETS_BODY": content["targets"]["body"],
        "TIMELINE_ITEMS": render_list(content["timeline"], "scope"),
        "NEXT_STEPS": render_list(content["next_steps"], "scope"),
        "FUNNEL": content["funnel"],
        "INCLUDED_LIST": content["included_list"],
        "TOOL_ROWS": tool_rows,
        "TOOLS_MONTHLY": tools_monthly,
        "SALESNAV_COST": salesnav_cost,
        "PRICING_ROWS": pricing_rows,
        "COMMISSION_EXAMPLES": examples,
        "COMMISSION_TERM_SENTENCE": commission_term,
        "ATTRIBUTION": cfg["pricing"].get(
            "attribution",
            "any deal where the first meeting was booked through our outreach",
        ),
        "LINKEDIN_EXPECT": render_linkedin(cfg["linkedin_option"], salesnav_cost),
    })

    # Setup fee is off by default. Both the callout and the
    # Stripe pay button appear only when a client config re-enables it.
    setup = cfg.get("setup_fee")
    if setup:
        if not cfg.get("payment", {}).get("stripe_url"):
            raise SystemExit(
                "setup_fee is set but payment.stripe_url is empty. The Pay button would "
                "render and open a blank tab. Add the Stripe link, or set setup_fee to null."
            )
        mapping["SETUP_CALLOUT"] = (
            f'  <div class="callout"><strong>Infrastructure Setup '
            f'(${money(setup["amount"])} one-time):</strong> {setup["description"]}</div>\n'
        )
        mapping["PAY_BUTTON"] = (
            '      <button class="btn btn-accent" id="pay-btn" disabled onclick="payNow()">\n'
            f'        💳 Pay Infrastructure Setup (${money(setup["amount"])})\n'
            '      </button>'
        )
    else:
        mapping["SETUP_CALLOUT"] = ""
        mapping["PAY_BUTTON"] = ""

    # Agreement paragraph is generated so the terms can never drift from the pricing table.
    client_co = mapping["CLIENT_COMPANY"]
    mapping["AGREEMENT_BODY"] = (
        f'{mapping["SENDER_COMPANY"]} will build and manage a cold email lead generation system '
        f'for {client_co} as described in this proposal. The engagement is {fee_sentence}. '
        f'Fees begin on the date this agreement is signed and are charged upfront on that date each '
        f'cycle. All tool subscription costs are billed directly to {client_co} at cost +3% and '
        f'remain their responsibility, including replacement mailboxes and domains as sending '
        f'infrastructure is refreshed. Either party may end the engagement with 30 days’ notice; '
        f'amounts already paid are not refunded. Additional targets or integrations outside this '
        f'scope may affect the timeline and costs.'
    )

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    output, missing = fill(template, mapping)

    # Hard stop, and write nothing. This document is a contract: shipping it with a
    # literal {{PLACEHOLDER}} visible to the client is worse than shipping nothing.
    # Scan the OUTPUT, not just fill()'s report — that catches a stray {{...}} left
    # inside a config's copy, which fill() never looks at.
    leftover = set(missing) | set(re.findall(r"\{\{[A-Z0-9_]+\}\}", output))
    if leftover:
        raise SystemExit(
            "unfilled placeholders, refusing to write:\n  "
            + "\n  ".join(sorted(leftover))
        )

    slug = mapping["CLIENT_COMPANY_SLUG"]
    out_dir = PUBLIC_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(output, encoding="utf-8")

    print(f"OK wrote public/{slug}/index.html")
    print(f"   pricing model: {cfg['pricing']['model']}")
    print(f"   tool prices last verified: {tool_costs['last_verified']}")
    print(f"   URL (after deploy): {base_url()}/{slug}")
    if not cfg["client"].get("company_slug"):
        print(f"   NOTE: slug was generated. Save \"company_slug\": \"{slug}\" "
              f"into {config_path} so redeploys keep this URL.")


if __name__ == "__main__":
    main()
