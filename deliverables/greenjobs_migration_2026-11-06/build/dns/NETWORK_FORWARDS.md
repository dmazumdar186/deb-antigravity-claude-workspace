# Network domain forwards (plan, 2026-11-20)

Internal. Public read-only lookups only; nothing was changed. Data: `network_forward_map.json` (the Bulk Redirects list is under `cloudflare_bulk_redirect_list`), DNS facts: `ZONE_INVENTORY_2026-11-20.md`.

## Name correction

The review lists `renewablejobsuk.com`. That name does not exist (DNS NXDOMAIN, no RDAP record). The home pages of greenjobs.co.uk and greenjobs.ie (fetched live today) link **renewableenergyjobsuk.com**, and so does every page of the 22 Sep redesign. The other seven names are correct and resolve.

## Forward map

| Old domain | Where its content is today | Target on new greenjobs.co.uk | Match |
|---|---|---|---|
| conservationjobsuk.com | Strategies; title "Conservation..." not fetched (HTTPS to www fails with a certificate-name error, see inventory) | `/ecology-jobs-uk/` | closest (no conservation page; 'conservation' is a keyword of the ecology sector) |
| ecologyjobsuk.com | Strategies, own page "Ecology Jobs and Ecologist Jobs in the United Kingdom" | `/ecology-jobs-uk/` | exact |
| environmentaljobsuk.com | Strategies, "Environmental Jobs and Environment Jobs in the United Kingdom" | `/jobs/?sector=Environmental%20science%20%26%20consulting` | closest (the only environmental landing is London-only) |
| renewableenergyjobsuk.com | Strategies, "Renewable Energy Jobs and Renewable Jobs in the United Kingdom" | `/renewable-energy-jobs-uk/` | exact |
| windjobsuk.com | Strategies, "Wind Turbine Jobs, Wind Farm Jobs & Offshore Wind Jobs in the UK" | `/jobs/?sector=Wind%20energy` | closest (alt: `/renewable-energy-jobs-uk/`) |
| solarjobsuk.com | Strategies, "Solar Jobs, Solar PV Jobs and Solar Panel Installer Jobs in the UK" | `/jobs/?sector=Solar%20energy` | closest (alt: `/renewable-energy-jobs-uk/`) |
| wastejobsuk.com | Strategies, "Waste Management Jobs, Recycling Jobs & Waste Jobs in the UK"; bare domain has no A record | `/jobs/?sector=Waste%20%26%20circular%20economy` | closest |
| waterjobsuk.com | Strategies, "Water Jobs, Water Treatment Jobs and Water Industry Jobs in the UK"; bare domain has no A record | `/jobs/?sector=Water%20%26%20flood` | closest |

All www hosts are an alias to the same Strategies name (`www-greenjobs-co-uk.cname.strategiesuk.net`), i.e. one site answering on eight host names. Each serves its own title today.

What the new build has: four UK landing pages (`ecology-jobs-uk`, `renewable-energy-jobs-uk`, `sustainability-jobs-uk`, `environmental-jobs-london`), a `/sectors/` index and a jobs board filterable with `?sector=<name>`. It has **no per-sector page** for conservation, environmental (UK-wide), wind, solar, waste or water, so six of the eight targets are the board filter or the nearest landing page, not a bespoke page. Full separate sector sites are the later quote already named in the review.

Assumption to confirm: paths are written as if the UK edition is the root of greenjobs.co.uk (`/ecology-jobs-uk/`). Staging serves it under `/uk/<slug>/index.html`. Fix the prefix and trailing-slash form once the production layout is decided, then re-run the check below.

## Cloudflare Bulk Redirects plan

- One list `greenjobs_network_forwards`, 8 items, each: source `<domain>/`, 301, include subdomains **on**, subpath matching **off**, preserve query string **off**, preserve path suffix **off** (old ASP deep links all land on the one sector target). JSON in `network_forward_map.json`.
- One rule enables the list: `http.request.full_uri in $greenjobs_network_forwards`.
- A Bulk Redirect only fires on traffic that reaches Cloudflare, so each network zone must also be **added to Cloudflare (nameserver move, path A)** with the apex and `www` as proxied (orange cloud) DNS records; the apex has no A record on wastejobsuk.com and waterjobsuk.com, so add a proxied placeholder there. No origin is needed.
- **Email records first.** All 8 network domains publish MX `0 smtp.secureserver.net.` and `10 mailstore1.secureserver.net.` with SPF `v=spf1 mx a include:secureserver.net -all` and a bare TXT code. Copy those into the Cloudflare zone (DNS only) before changing nameservers, or any forwarders or mailboxes on those domains stop. Ask Diana whether any are in use. Registrar is 123-Reg for all 8; DNS is at GoDaddy nameservers (`domaincontrol.com`), a different party from the registrar's own panel, so the nameserver change is done at 123-Reg.
- Before 6 Dec the zones can move on Mon 30 Nov with the greenjobs zones, with the redirect list enabled on Thu 3 Dec at switch time. Until then the `www` aliases keep pointing at Strategies.

## Check after loading (read-only)

`curl -sI https://www.<domain>/` returns 301 with the target in `location`, for the bare and `www` names of all 8, and `curl -sI "http://<domain>/old/page.asp"` returns the same target.
