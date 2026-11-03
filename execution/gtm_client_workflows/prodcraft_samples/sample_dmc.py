"""
sample_dmc.py
description: Content for the DMC incentive trip proposal sample (fictional, Lisbon, 120 qualifiers, 4 nights).
inputs: none (all content is fictional and defined here).
outputs: render.Doc via build().
"""
from render import Doc, table, money, built_from

BRIEF = ("Draxmere Medical is rewarding 120 top sales qualifiers with a 4-night incentive trip to Lisbon in May 2027. "
         "Mix of culture, food and one wow evening; nothing too sporty. Guests fly in from across Europe and the US. "
         "Please send a program, hotel options and a per-person price.")

PAX = 120
NIGHTS = 4
HOTELS = [  # key, name, rate per room night (single occupancy)
    ("A", "Riverside five-star", 520),
    ("B", "Design hotel, Chiado", 410),
    ("C", "Coastal resort, Cascais", 360),
]
COMMON = [
    ("Arrival and departure transfers (shared, timed to flight banks)", 78),
    ("Welcome dinner with drinks, day 1", 140),
    ("Day 2 city experience: vintage tram, guided walks, lunch", 165),
    ("Day 3 Sintra and coast day: coaches, guides, palace entry, lunch", 210),
    ("Day 4 gala dinner at exclusive-use venue, with entertainment", 295),
    ("Welcome gift and two room drops", 65),
    ("On-site staff and hospitality desk (5 days)", 92),
    ("Program management fee", 120),
]
COMMON_PP = sum(v for _, v in COMMON)


def pp(rate: int) -> int:
    return rate * NIGHTS + COMMON_PP


def day(label, title, slots):
    s = "".join(f'<div class="slot"><div class="tm">{t}</div><p>{x}</p></div>' for t, x in slots)
    return f'<div class="day"><div class="d">{label}</div><div><h3 style="margin:0 0 6px">{title}</h3>{s}</div></div>'


def build() -> Doc:
    d = Doc("dmc_trip_proposal", "Incentive Program · Lisbon, May 2027", "Saltmarrow Journeys DMC", "a4", "#9a4e34")

    d.add(f"""
<div>
  <div class="kicker">Incentive program proposal · prepared for Draxmere Medical</div>
  <h1>Lisbon, light and tide<br>President's Club 2027</h1>
  <p class="lede">Four nights in Lisbon for 120 qualifiers: river light, old-town food, a day on the Sintra coast and a gala evening the group will talk about all year.</p>
</div>
<div class="grid4">
  <div class="card tint stat"><div class="k">Guests</div><div class="n">{PAX}</div></div>
  <div class="card tint stat"><div class="k">Dates</div><div class="n">12–16 May</div></div>
  <div class="card tint stat"><div class="k">Nights</div><div class="n">{NIGHTS}</div></div>
  <div class="card tint stat"><div class="k">From, per person</div><div class="n">{money(min(pp(h[2]) for h in HOTELS), '€')}</div></div>
</div>
<div class="meta"><div>Prepared for<b>Head of Sales Operations, Draxmere Medical</b></div><div>Prepared by<b>Program Director, Saltmarrow Journeys DMC</b></div><div>Date<b>3 Nov 2026</b></div></div>
{built_from(BRIEF)}""", "cover")

    d.add("""
<div class="kicker">01 · Program overview</div>
<h2>A reward that feels personal, not packaged</h2>
<p class="lede">Lisbon in May is warm, bright and walkable, with direct flights from most European hubs and from several US gateways. The program balances group moments with free time, so qualifiers feel rewarded, not managed.</p>
<div class="grid2">
  <div class="card"><h3>The shape of the trip</h3>
  <ul><li><b>Day 1</b> · arrive, settle in, welcome dinner with a view over the river.</li>
  <li><b>Day 2</b> · Lisbon by tram and on foot, long lunch, free afternoon.</li>
  <li><b>Day 3</b> · Sintra palaces and the Atlantic coast, free evening.</li>
  <li><b>Day 4</b> · free morning, awards and gala dinner at an exclusive-use venue.</li>
  <li><b>Day 5</b> · late breakfast and departures.</li></ul></div>
  <div class="card"><h3>Why it works for a sales group</h3>
  <ul><li>Two group meals that feel like events, two that feel like a night out with friends.</li>
  <li>Free time every day, with a concierge desk to book anything extra.</li>
  <li>The awards moment sits inside the gala, not in a hotel ballroom.</li>
  <li>Every activity is low-effort physically and works for partners too.</li></ul></div>
</div>
<div class="card tint" style="margin-top:14px"><h3>Program at a glance</h3>
<p style="margin:0">4 group dinners or lunches · 2 guided experiences · 1 gala with entertainment · 8 on-site staff plus a program director · 24/7 hotel hospitality desk · all ground transport included.</p></div>""")

    d.add(f"""
<div class="kicker">02 · Itinerary</div>
<h2>Day by day</h2>
<div class="itin">
{day("Day 1 · Wed 12", "Arrivals and welcome", [
    ("All day", "Meet-and-greet at Lisbon airport; shared transfers timed to flight banks; welcome desk in the hotel lobby."),
    ("15:00", "Rooms ready, welcome gift in every room."),
    ("19:30", "Welcome dinner on a rooftop terrace over the Tagus: Portuguese tasting menu, local wines, a fado trio."),
])}
{day("Day 2 · Thu 13", "Lisbon by tram and on foot", [
    ("09:30", "Groups of 20 board private vintage trams through Alfama and Graça with a local guide."),
    ("11:30", "Walk through the old town; custard tart stop at a historic bakery."),
    ("13:00", "Long lunch at a riverside restaurant in Belém."),
    ("15:00", "Free afternoon. Optional: tile-painting workshop, river sailing, or shopping in Chiado."),
    ("Evening", "Free. Concierge desk books restaurants; suggested list in the guest app."),
])}
</div>""")

    d.add(f"""
<div class="kicker">02 · Itinerary, continued</div>
<div class="itin">
{day("Day 3 · Fri 14", "Sintra palaces and the Atlantic coast", [
    ("09:00", "Coaches to Sintra; guided visit to a hilltop palace and gardens."),
    ("13:00", "Seafood lunch on the cliffs near Cabo da Roca."),
    ("15:30", "Coastal drive through Cascais; stop for a walk on the promenade."),
    ("17:30", "Return to the hotel. Free evening."),
])}
{day("Day 4 · Sat 15", "Free morning, awards and gala", [
    ("Morning", "Free. Optional spa slots and a guided food market tour (book via the hospitality desk)."),
    ("18:30", "Coaches to an exclusive-use 18th-century palace venue."),
    ("19:00", "Cocktails in the garden; arrival photos."),
    ("20:00", "Gala dinner: four courses, Portuguese wine pairing."),
    ("21:30", "President's Club awards, hosted by your leadership team; staged and lit by our production partner."),
    ("22:15", "Live band and late bar until 01:00; shuttle back from 23:00."),
])}
{day("Day 5 · Sun 16", "Departures", [
    ("Morning", "Late breakfast; checkout extended to 12:00 for the group."),
    ("From 08:00", "Shared transfers to the airport timed to flight banks; desk open until the last guest leaves."),
])}
</div>
<div class="card tint" style="margin-top:12px"><h3>Optional add-ons (priced on request)</h3>
<p style="margin:0">Pre- or post-stay nights at the group rate · private sunset sailing for the top ten · partner program on day 4 morning · branded gifts from local makers.</p></div>""")

    hotel_text = {
        "A": ("Five-star on the river, e.g. a waterfront property in the Cais do Sodré area.",
              ["All rooms with river or city view", "Private room for the welcome desk and briefings", "Spa and rooftop pool", "10 minutes on foot to the old town"]),
        "B": ("Boutique design hotel in Chiado, e.g. a converted 19th-century building.",
              ["Characterful rooms, smaller footprint", "Whole-hotel buyout possible for 120", "Walking distance to everything in the program", "Rooftop bar for a private hospitality evening"]),
        "C": ("Coastal resort in Cascais, e.g. an ocean-front five-star 30 minutes from Lisbon.",
              ["Sea-view rooms and a large pool deck", "Beach and promenade on the doorstep", "Adds 30–40 minutes of coach time on days 2 and 4", "Best for a slower, resort-style feel"]),
    }
    cards = ""
    for k, name, rate in HOTELS:
        desc, pts = hotel_text[k]
        cards += (f'<div class="card"><div class="kicker">Option {k}</div><h3>{name}</h3><p>{desc}</p>'
                  f'<ul>{"".join(f"<li>{p}</li>" for p in pts)}</ul>'
                  f'<p style="margin:0"><span class="pill">{money(rate, "€")} per room night</span></p></div>')
    d.add(f"""
<div class="kicker">03 · Hotel options</div>
<h2>Three ways to stay</h2>
<p class="lede">All three hold 120 single-occupancy rooms for 12–16 May 2027 at the rates shown, including breakfast and city tax. Named properties are confirmed with the contract; descriptions below are examples of the category.</p>
<div class="grid3">{cards}</div>
<p class="note" style="margin-top:12px">Our recommendation: <b>Option A</b>. The river location keeps every transfer short and gives the group a shared view to come back to each evening.</p>""")

    rows = [(["<b>Per person</b>", "", "", ""], "sec")]
    rows.append([f"Hotel, {NIGHTS} nights single occupancy, breakfast and city tax"] + [money(r * NIGHTS, '€') for _, _, r in HOTELS])
    rows += [[lab] + [money(v, '€')] * 3 for lab, v in COMMON]
    rows.append((["<b>Total per person</b>"] + [f"<b>{money(pp(r), '€')}</b>" for _, _, r in HOTELS], "sub"))
    rows.append(([f"<b>Program total ({PAX} guests)</b>"] + [f"<b>{money(pp(r) * PAX, '€')}</b>" for _, _, r in HOTELS], "total"))
    d.add(f"""
<div class="kicker">04 · Pricing</div>
<h2>Per person and total, by hotel option</h2>
<p class="lede">Illustrative EUR figures, based on {PAX} guests in single rooms. Everything except the hotel is the same across the three options.</p>
{table(["", "Option A", "Option B", "Option C"], rows, align=["l","r","r","r"], widths=["55%","15%","15%","15%"])}
<div class="grid2" style="margin-top:6px">
  <div class="card tint"><p style="margin:0"><b>Group size changes.</b> Per-person prices hold between 110 and 130 guests. Below 110, the gala venue and staffing are re-quoted.</p></div>
  <div class="card tint"><p style="margin:0"><b>Taxes.</b> Prices include Portuguese VAT where it applies. International flights are not included.</p></div>
</div>""")

    inc = ["4 nights' accommodation, single occupancy, with breakfast and city tax", "All airport transfers, timed to flight banks",
           "Welcome dinner, day 2 lunch, day 3 lunch and gala dinner with drinks as described", "Guides, entrance fees and private trams on day 2",
           "Gala venue hire, entertainment, awards staging and lighting", "Welcome gift and two room drops", "On-site staff, hospitality desk and guest app"]
    exc = ["International flights and travel insurance", "Meals not listed (day 2 and 3 dinners are free evenings)",
           "Optional activities and spa", "Room service, minibar and personal expenses", "Gratuities to hotel staff beyond the group arrangement"]
    d.add(f"""
<div class="kicker">05 · Inclusions and logistics</div>
<div class="grid2">
  <div><h2>Included</h2><ul>{''.join(f'<li>{i}</li>' for i in inc)}</ul></div>
  <div><h2>Not included</h2><ul>{''.join(f'<li>{e}</li>' for e in exc)}</ul></div>
</div>
<h2 style="margin-top:8px">Logistics</h2>
{table(["Area", "How we handle it"], [
    ["Arrivals", "Flight manifest from you 6 weeks out. Shared transfers in 8- and 49-seat vehicles, grouped by arrival within 60 minutes; private car for anyone arriving outside the banks."],
    ["Staffing", "1 program director plus 8 on-site staff, one per 15 guests. Two staff travel with every coach; one stays at the hotel desk."],
    ["Group movements", "Coaches of 49 seats; three coaches plus one minibus on days 3 and 4. Every coach has a named host and a headcount on board."],
    ["Guest care", "24/7 hotel desk and phone line, guest app with the day's plan, dietary and access needs collected at registration."],
    ["Safety", "Licensed guides and coach operators, insurance certificates on file, a local medical contact on call."],
], align=["l","l"], widths=["20%","80%"])}""")

    d.add(f"""
<div class="kicker">06 · Terms</div>
<h2>Booking terms</h2>
<ul>
<li><b>Validity.</b> This proposal and the hotel rates are held for 21 days from 3 November 2026, subject to availability on signing.</li>
<li><b>Payment.</b> 30% on signing; 40% 90 days before arrival; 30% 30 days before arrival.</li>
<li><b>Rooming list.</b> Final names 30 days before arrival. Up to 10% of rooms can be released without charge until 60 days before arrival.</li>
<li><b>Cancellation.</b> More than 120 days: deposit retained. 120–61 days: 50% of the program total. 60 days or less: 100%.</li>
<li><b>Changes.</b> Changes after signing are confirmed in writing with any cost before they are made.</li>
</ul>
<div class="kicker" style="margin-top:14px">07 · Next steps</div>
<div class="grid3">
  <div class="card"><div class="kicker">Step 1</div><h3>Pick a hotel</h3><p>A 30-minute call to agree the option and any program changes.</p></div>
  <div class="card"><div class="kicker">Step 2</div><h3>Hold the rooms</h3><p>We place a courtesy hold on 120 rooms for 7 days while the contract is signed.</p></div>
  <div class="card"><div class="kicker">Step 3</div><h3>Sign and launch</h3><p>Signed contract and deposit; we send the guest registration link within 5 working days.</p></div>
</div>
<div class="card tint" style="margin-top:12px"><p style="margin:0"><b>Contact.</b> Program Director, Saltmarrow Journeys DMC · programs@saltmarrow.example</p></div>""")
    return d
