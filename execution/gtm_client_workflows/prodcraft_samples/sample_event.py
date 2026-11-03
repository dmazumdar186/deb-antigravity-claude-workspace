"""
sample_event.py
description: Content for the EVENT/AV pitch deck sample (fictional SKO 2027, Las Vegas).
inputs: none (all content is fictional and defined here).
outputs: render.Doc via build().
"""
from render import Doc, table, money, built_from, gantt

BRIEF = ("Velloran Software needs its Sales Kickoff 2027 produced: 600 sellers and leaders, Las Vegas, three days "
         "in mid-January 2027. One general session room, six breakouts, an awards night. We want it to feel "
         "bigger than last year without the budget doubling. Please send concept, staging, AV and a budget range.")

TIERS = ["Good", "Better", "Best"]
LINES = [  # label, good, better, best
    ("Creative & show content (theme, graphics, films)", 48_000, 72_000, 110_000),
    ("Set & staging (stage, thrust, scenic, drape)", 85_000, 128_000, 185_000),
    ("LED & video (main wall, IMAG, cameras, playback)", 96_000, 142_000, 214_000),
    ("Audio (line array, RF mics, monitors)", 38_000, 46_000, 58_000),
    ("Lighting (stage wash, moving lights, room)", 42_000, 61_000, 88_000),
    ("Breakout AV (6 rooms, 3 days)", 36_000, 42_000, 54_000),
    ("Awards night production", 28_000, 45_000, 72_000),
    ("Crew & labor (incl. venue labor estimate)", 74_000, 92_000, 118_000),
    ("Production management & show calling", 45_000, 52_000, 60_000),
    ("Freight, travel & per diems", 22_000, 26_000, 31_000),
]
TOTALS = [sum(l[i] for l in LINES) for i in (1, 2, 3)]
ATTENDEES = 600


def stage_diagram() -> str:
    a = "var(--accent)"
    seats = "".join('<div style="background:#d8d1c4;border-radius:2px"></div>' for _ in range(50))
    return f"""
<div class="stage">
  <div class="lbl" style="top:2%;left:0;right:0">BACK OF HOUSE · video village · green room</div>
  <div class="el" style="top:8%;left:20%;width:60%;height:10%;background:{a}">MAIN LED WALL · 48 × 13.5 ft</div>
  <div class="el" style="top:9.5%;left:4%;width:13%;height:7%;background:#5b6068">IMAG L</div>
  <div class="el" style="top:9.5%;right:4%;width:13%;height:7%;background:#5b6068">IMAG R</div>
  <div class="el" style="top:20%;left:22%;width:56%;height:12%;background:#16181c">STAGE · 56 × 24 ft · 3 ft high</div>
  <div class="el" style="top:32%;left:43%;width:14%;height:13%;background:#16181c">THRUST</div>
  <div class="lbl" style="top:47%;left:0;right:0">600 seats · crescent theatre rows · centre aisle to the thrust</div>
  <div style="position:absolute;top:53%;left:8%;right:8%;height:28%;display:grid;grid-template-columns:repeat(5,1fr) 6% repeat(5,1fr);grid-auto-rows:1fr;gap:5px">
    {''.join(('<div></div>' if i % 11 == 5 else '<div style="background:#d8d1c4;border-radius:2px"></div>') for i in range(55))}
  </div>
  <div class="el" style="bottom:4%;left:25%;width:50%;height:8%;background:#5b6068">FOH · audio · lighting · cameras</div>
</div>"""


def build() -> Doc:
    d = Doc("event_av_pitch_deck", "Sales Kickoff 2027 · Production proposal", "Merrow Lane Live", "deck", "#2b3a67")

    d.add(f"""
<div>
  <div class="kicker">Production proposal · prepared for Velloran Software</div>
  <h1>Sales Kickoff 2027<br>“Closer Together”</h1>
  <p class="lede">Three days, 600 sellers, one room that feels like the start of a winning year. Concept, staging, AV and a budget in three tiers.</p>
  <div class="grid4" style="margin-top:6px">
    <div class="card tint"><p style="margin:0"><b>Concept</b><br>“Closer Together” and three signature moments</p></div>
    <div class="card tint"><p style="margin:0"><b>The room</b><br>Stage, LED and seating plan for 600</p></div>
    <div class="card tint"><p style="margin:0"><b>The show</b><br>Run of show, AV spec, timeline</p></div>
    <div class="card tint"><p style="margin:0"><b>The money</b><br>Good, better, best budget in USD</p></div>
  </div>
</div>
<div class="grid2" style="align-items:end">
  <div class="meta"><div>Event<b>12–14 Jan 2027</b></div><div>Location<b>Las Vegas, NV</b></div><div>Attendees<b>600</b></div></div>
  {built_from(BRIEF)}
</div>""", "cover")

    d.add("""
<div class="kicker">01 · The brief</div>
<div class="oneliner">Make 600 sellers leave Las Vegas believing in the 2027 number, in a show that feels bigger than last year without the budget doubling.</div>
<div class="grid4">
  <div class="card tint stat"><div class="k">Audience</div><div class="n">600</div><p>Account executives, SEs, managers and the exec team</p></div>
  <div class="card tint stat"><div class="k">Format</div><div class="n">3 days</div><p>General sessions, 6 breakouts, awards night</p></div>
  <div class="card tint stat"><div class="k">Dates</div><div class="n">Jan 12–14</div><p>Load-in Jan 10–11, strike night of Jan 14</p></div>
  <div class="card tint stat"><div class="k">Must land</div><div class="n">1 message</div><p>The 2027 plan, the new product line, and who won 2026</p></div>
</div>
<h3 style="margin-top:22px">What success looks like</h3>
<ul><li>Every seller can repeat the 2027 plan in one sentence by the end of day 1.</li>
<li>Breakouts run on time with no dead air between sessions.</li><li>Awards night is the moment people post about, not the one they leave early.</li></ul>""")

    d.add("""
<div class="kicker">02 · Concept</div>
<h2>“Closer Together”</h2>
<p class="lede">A theme that works twice: closer to the customer, and closer as one team after a year of growth through hiring. Everything on stage points the same way, toward the people in the room.</p>
<div class="grid3">
  <div class="card"><h3>Look</h3><p>Warm neutrals with one strong blue. Big type, short lines. Every graphic is built to read from the back row.</p></div>
  <div class="card"><h3>Story arc</h3><p>Day 1: where we are and where we go. Day 2: how we win, deal by deal. Day 3: who made it happen. Each day opens with a 90-second film.</p></div>
  <div class="card"><h3>Room energy</h3><p>Crescent seating and a thrust bring the stage 20 ft closer to the audience. Walk-in music and lighting change by day.</p></div>
</div>
<h3 style="margin-top:18px">Signature moments</h3>
<div class="grid3">
  <div class="card tint"><p><b>The number reveal.</b> The 2027 target builds across the full LED wall, region by region, as each sales leader walks on.</p></div>
  <div class="card tint"><p><b>Customer on stage.</b> A live 12-minute conversation with a customer, shot on three cameras for IMAG.</p></div>
  <div class="card tint"><p><b>Awards walk.</b> Winners enter through the audience on a lit runway to the thrust.</p></div>
</div>""")

    d.add(f"""
<div class="kicker">03 · General session look</div>
<div class="split">
  <div style="display:flex;flex-direction:column;min-height:0">
    <h2>One wide, warm stage</h2>
    <p class="lede">A 56 ft stage with a full-width LED wall as the set itself. No scenic flats to haul; the wall changes the look for every segment.</p>
    <ul>
      <li><b>Main LED wall</b> 48 × 13.5 ft, 2.6 mm pitch, carries keynote graphics, films and live camera.</li>
      <li><b>Two IMAG screens</b> flank the wall so the back rows see faces, not dots.</li>
      <li><b>Thrust stage</b> 12 × 16 ft for fireside chats and the awards walk.</li>
      <li><b>Lectern + confidence monitors</b> downstage, plus a countdown clock for every presenter.</li>
      <li><b>FOH</b> centred two-thirds back, with sightline to the whole stage.</li>
    </ul>
    <div class="card tint" style="margin-top:auto"><p style="margin:0"><b>Room assumptions.</b> Ballroom about 30,000 sq ft, 28 ft to the rigging grid, theatre seating for 600 with room for camera risers. Confirmed at the site visit.</p></div>
  </div>
  <div style="min-height:0">{stage_diagram()}</div>
</div>""")

    ros = [
        ("7:00", "Breakfast and walk-in", "Ballroom foyer", "Walk-in music, loop on LED"),
        ("8:30", "Opening film + welcome", "General session", "90-second film, CRO on stage"),
        ("8:45", "CEO keynote: the 2027 plan", "General session", "Number reveal, IMAG, 2 lav mics"),
        ("9:30", "Product line launch", "General session", "Demo on LED, playback from video village"),
        ("10:15", "Break", "Foyer", "Countdown on screens"),
        ("10:35", "Customer on stage", "General session", "Thrust, 3 cameras, 2 handhelds"),
        ("11:15", "Regional leaders panel", "General session", "4 seats on thrust"),
        ("12:00", "Lunch", "Hall B", "Background music"),
        ("13:15", "Breakouts, round 1 (6 rooms)", "Breakout level", "Projector + PA per room"),
        ("14:30", "Breakouts, round 2", "Breakout level", "Room turns in 15 min"),
        ("15:45", "Day 1 close: commitments", "General session", "Live poll on LED"),
        ("18:30", "Welcome reception", "Pool terrace", "DJ, uplighting"),
    ]
    d.add(f"""
<div class="kicker">04 · Run of show</div>
<h2>Day 1 skeleton · Tuesday 12 January</h2>
{table(["Time", "Segment", "Room", "Production notes"], ros, align=["l","l","l","l"], widths=["9%","37%","20%","34%"])}
<p class="small">Day 2 is deal clinics and enablement in breakouts with a short general session; day 3 morning is the closing general session, evening is awards night. Full show script follows on approval.</p>""")

    d.add("""
<div class="kicker">04 · Run of show, continued</div>
<h2>Days 2 and 3 at a glance</h2>
<div class="grid2" style="margin-top:6px">
  <div class="card"><div class="kicker">Wednesday 13 January</div><h3>Day 2 · How we win</h3>
  <ul><li>8:30 short general session: two customer wins told by the reps who closed them.</li>
  <li>9:15 to 15:30 deal clinics and enablement in six breakouts, four rounds.</li>
  <li>Lunch by region, with leaders hosting tables.</li>
  <li>16:00 product lab in the foyer: demo pods, run by SEs.</li>
  <li>Evening free; regional dinners booked by the client.</li></ul></div>
  <div class="card"><div class="kicker">Thursday 14 January</div><h3>Day 3 · Who made it happen</h3>
  <ul><li>9:00 closing general session: the 2027 plan by region, CEO close.</li>
  <li>11:30 finish; afternoon free for travel or team time.</li>
  <li>18:30 awards night: cocktails, dinner for 600, awards walk on the lit runway.</li>
  <li>21:30 live band and late bar until midnight.</li>
  <li>Strike begins at 00:30; out of the venue by 08:00.</li></ul></div>
</div>
<p class="small" style="margin-top:12px">The general session room flips to awards night between 12:00 and 17:00 on day 3; the stage, LED wall and FOH stay in place.</p>""")

    spec = [
        ("Video", "Main LED wall", "48 × 13.5 ft, 2.6 mm, with processor and spare panels"),
        ("Video", "IMAG screens (2)", "16:9 projection 9 × 16 ft, 20K lumen projectors"),
        ("Video", "Cameras", "3 broadcast cameras (2 on tripods, 1 handheld), switcher, record"),
        ("Video", "Playback", "Redundant playback servers, confidence monitors, countdown clock"),
        ("Audio", "PA", "Line array L/R with front fills and delays for 600 seats"),
        ("Audio", "Microphones", "8 RF lavalier, 4 RF handheld, 1 lectern mic, audience mic runner"),
        ("Lighting", "Stage", "Front and back wash, 24 moving heads, haze, key light for camera"),
        ("Lighting", "Room", "Uplighting on room walls, house light control"),
        ("Breakouts", "6 rooms", "Projector + screen, 2 mics, small PA, laptop switcher, room tech per 2 rooms"),
        ("Staging", "Stage + thrust", "56 × 24 ft at 3 ft, 12 × 16 ft thrust, stairs, skirting, ADA ramp"),
        ("Crew", "Show crew", "Producer, stage manager, show caller, A1, V1, L1, camera ops, stagehands"),
    ]
    d.add(f"""
<div class="kicker">05 · AV & staging spec</div>
<h2>What goes in the room</h2>
{table(["Area", "Item", "Specification"], spec, align=["l","l","l"], widths=["12%","20%","68%"])}
<p class="small">Spec shown is the “Better” tier. Final quantities confirmed after the venue site visit and rigging plot review.</p>""")

    rows = [[lab] + [money(v) for v in vals] for lab, *vals in LINES]
    rows.append(([ "<b>Total production</b>"] + [f"<b>{money(t)}</b>" for t in TOTALS], "total"))
    rows.append((["Per attendee (÷ 600)"] + [money(t / ATTENDEES) for t in TOTALS], "muted"))
    d.add(f"""
<div class="kicker">06 · Budget</div>
<h2>Three ways to do it</h2>
<div style="display:grid;grid-template-columns:2.2fr 1fr;gap:24px">
  <div>{table(["Line", "Good", "Better", "Best"], rows, align=["l","r","r","r"], widths=["52%","16%","16%","16%"])}</div>
  <div>
    <div class="card tint"><h3>Good</h3><p>Same room, smaller wall, one film, standard awards set.</p></div>
    <div class="card tint" style="margin-top:8px;border-left:3px solid var(--accent)"><h3>Better · recommended</h3><p>Full-width wall, thrust, three films, lit awards walk.</p></div>
    <div class="card tint" style="margin-top:8px"><h3>Best</h3><p>Curved wall, kinetic lighting, live-music awards night, extra content.</p></div>
  </div>
</div>
<p class="small">Illustrative USD figures. Excludes venue rental, food and beverage, attendee travel, venue in-house rigging and power fees, and sales tax.</p>""")

    weeks = ["Nov 9", "Nov 16", "Nov 23", "Nov 30", "Dec 7", "Dec 14", "Dec 21", "Dec 28", "Jan 4", "Jan 11"]
    tl = [
        ("Concept sign-off and budget lock", 0, 1),
        ("Equipment holds confirmed, crew booked", 1, 2),
        ("Site visit, rigging plot, venue contracts", 1, 3),
        ("Show content: films, graphics, templates", 2, 7),
        ("Speaker briefings and slide deadlines", 3, 5),
        ("Final run of show and show script", 6, 8),
        ("Load-in, tech and rehearsals (Jan 10–11)", 8, 9),
        ("Show days (Jan 12–14) and strike", 9, 9),
    ]
    d.add(f"""
<div class="kicker">07 · Production timeline</div>
<h2>From sign-off to show day</h2>
<p class="lede" style="margin-bottom:10px">Ten weeks is tight for 600 people in January. The plan below works if the concept and tier are agreed by 20 November.</p>
{gantt(weeks, tl)}
<div class="grid3" style="margin-top:10px">
  <div class="card tint"><p style="margin:0"><b>20 Nov</b> · concept and tier approved, deposit received.</p></div>
  <div class="card tint"><p style="margin:0"><b>11 Dec</b> · all presenter slides in; content locked 23 Dec.</p></div>
  <div class="card tint"><p style="margin:0"><b>11 Jan</b> · full dress rehearsal with every presenter.</p></div>
</div>""")

    roles = [("Executive producer", "Owns the budget and is your single point of contact from sign-off to wrap."),
             ("Show producer", "Runs content, speakers and rehearsals; writes the show script."),
             ("Technical director", "Owns the AV design, the rigging plot and the venue relationship."),
             ("Stage manager + show caller", "Keep every segment on time and every presenter ready."),
             ("Content team", "Films, show graphics and presenter templates in your brand.")]
    d.add(f"""
<div class="kicker">08 · Team & how we work</div>
<h2>One producer, one plan, no surprises</h2>
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:4px">
{''.join(f'<div class="card tint"><h3>{r}</h3><p style="margin:0">{t}</p></div>' for r, t in roles)}
</div>
<h3 style="margin-top:22px">How we work</h3>
<div class="grid2">
  <ul><li>Weekly 30-minute call from sign-off, and a shared tracker with every open decision and its owner.</li>
  <li>Budget changes shown before they are spent, never after.</li></ul>
  <ul><li>Every speaker gets one rehearsal slot on the real stage, with a confidence monitor and clock.</li>
  <li>Wrap report within ten working days of show close, with final costs against budget.</li></ul>
</div>""")

    d.add("""
<div class="kicker">09 · Next steps</div>
<h2>To hold January 2027 crew and equipment</h2>
<div class="grid3" style="margin-top:8px">
  <div class="card"><div class="kicker">Step 1</div><h3>Choose a tier</h3><p>A 45-minute call to walk the budget and agree what moves between tiers.</p></div>
  <div class="card"><div class="kicker">Step 2</div><h3>Site visit</h3><p>Our technical director meets the venue to confirm rigging, power and load-in times.</p></div>
  <div class="card"><div class="kicker">Step 3</div><h3>Sign and hold</h3><p>Signed agreement and 30% deposit secure the crew and the LED stock for your dates.</p></div>
</div>
<h3 style="margin-top:22px">Decisions we need from you by 20 November</h3>
<div class="grid4">
  <div class="card"><p style="margin:0"><b>Tier</b><br>Good, better or best, and any lines to move between them</p></div>
  <div class="card"><p style="margin:0"><b>Venue contact</b><br>Name at the hotel for rigging, power and load-in</p></div>
  <div class="card"><p style="margin:0"><b>Speakers</b><br>Confirmed list for the three general sessions</p></div>
  <div class="card"><p style="margin:0"><b>Awards</b><br>Number of categories and winners walking on</p></div>
</div>
<div class="card tint" style="margin-top:16px"><p><b>Validity.</b> Pricing holds for 30 days. January is peak season in Las Vegas; LED and crew availability is confirmed only on deposit.</p>
<p style="margin:0"><b>Contact.</b> Executive Producer, Merrow Lane Live · producer@merrowlane.example</p></div>""")
    return d
