"""
sample_fitout_uk.py
description: Content for the UK Cat B office fit-out tender submission sample (fictional, London, 1,300 m2).
inputs: none (all content is fictional and defined here).
outputs: render.Doc via build().
"""
from render import Doc, table, money, built_from, gantt

BRIEF = ("Pellwyn Harcourt LLP is fitting out levels 4 and 5 of 22 Calloway Street, London EC2 — about 1,300 m² NIA, "
         "Cat A complete. Tender pack attached: designer's drawings, specification and pricing schedule. Practical "
         "completion needed by May 2027. Return your priced tender with programme and qualifications.")

M2 = 1_300
PRELIMS = 168_000
WORKS = [
    ("1", "Strip-out of Cat A finishes where affected", 38_500),
    ("2", "Partitions, drylining and acoustic upgrades", 142_000),
    ("3", "Glazed partitions and glazed doors", 126_000),
    ("4", "Internal doors and ironmongery", 64_800),
    ("5", "Ceiling modifications, rafts and bulkheads", 72_400),
    ("6", "Floor finishes (carpet tile, LVT, entrance matting)", 118_600),
    ("7", "Joinery (reception desk, tea points, lockers, booths)", 164_000),
    ("8", "Decorations and wall finishes", 46_200),
    ("9", "Mechanical adaptations (FCUs, extract, controls)", 152_000),
    ("10", "Electrical adaptations (lighting, small power, floor boxes)", 138_500),
    ("11", "Fire alarm and life-safety adaptations", 28_700),
    ("12", "Data containment (cabling by client's IT supplier)", 22_400),
    ("13", "Builder's work in connection with services", 18_600),
    ("14", "Signage and glazing manifestation", 9_800),
]
WORKS_SUB = sum(w[2] for w in WORKS)
OHP = round((PRELIMS + WORKS_SUB) * 0.06)
PSUMS = [
    ("PS1", "Landlord's surveyor, licence for alterations and approval fees", 12_000),
    ("PS2", "Feature lighting to reception and client suite", 25_000),
    ("PS3", "Out-of-hours working required by building management", 15_000),
    ("PS4", "Making good to Cat A defects found after strip-out", 10_000),
]
PS_SUB = sum(p[2] for p in PSUMS)
TENDER = PRELIMS + WORKS_SUB + OHP + PS_SUB


def build() -> Doc:
    d = Doc("fitout_uk_tender_submission", "Tender Submission · 22 Calloway Street, Levels 4–5", "Ashcombe Rook Interiors Ltd", "a4", "#2f4f4f")

    facts = [
        ("Project", "Cat B office fit-out, levels 4 and 5"),
        ("Address", "22 Calloway Street, London EC2 (fictional)"),
        ("Area", f"{M2:,} m² NIA across two floors"),
        ("Tender documents", "Designer's drawings rev. C, specification and pricing schedule, 9 Oct 2026"),
        ("Form of contract", "JCT Minor Works Building Contract 2016, as amended"),
        ("Practical completion", "Friday 14 May 2027"),
    ]
    d.add(f"""
<div>
  <div class="kicker">Tender submission · Ref. ARI-T-2611 · 3 November 2026</div>
  <h1>Cat B fit-out, levels 4–5<br>for Pellwyn Harcourt LLP</h1>
  <p class="lede">Our priced tender for the 1,300 m² Cat B fit-out, with programme to practical completion on 14 May 2027, preliminaries, provisional sums and the qualifications behind the price.</p>
</div>
<div class="grid2">
  <div class="card tint stat"><div class="k">Tender sum (excl. VAT)</div><div class="n">{money(TENDER, '£')}</div>
    <p class="small" style="margin:4px 0 0">{money(TENDER / M2, '£')} per m² NIA · validity 60 days</p></div>
  <div class="card tint stat"><div class="k">Contract period</div><div class="n">17 weeks</div>
    <p class="small" style="margin:4px 0 0">Start on site 18 Jan 2027 · PC 14 May 2027</p></div>
</div>
{table(["", ""], facts, align=["l","l"], widths=["30%","70%"])}
<div class="meta"><div>Submitted to<b>Project Manager, for Pellwyn Harcourt LLP</b></div><div>Submitted by<b>Bid Director, Ashcombe Rook Interiors Ltd</b></div></div>
{built_from(BRIEF)}""", "cover")

    d.add("""
<div class="kicker">01 · Scope and approach</div>
<h2>Our understanding of the works</h2>
<p class="lede">The building is delivered to Cat A: raised floor, suspended ceiling, LED lighting, four-pipe fan coils and a fire alarm system. Our works adapt it to the designer's Cat B layout across both floors.</p>
<div class="grid2">
<div>
<h3>Level 4 · client and meeting floor</h3>
<ul><li>Reception with feature desk, waiting lounge and glazed client suite of five meeting rooms.</li>
<li>Main tea point and breakout with banquette seating and joinery.</li>
<li>Two quiet rooms, wellbeing room and a comms room with dedicated cooling.</li></ul>
<h3>Level 5 · workplace floor</h3>
<ul><li>Open-plan desks for 96, with lockers and two focus booths.</li>
<li>Six partner offices with glazed fronts, two team rooms and a satellite tea point.</li></ul>
</div>
<div>
<h3>Services adaptations</h3>
<ul><li>Re-position and add fan coil units to suit cellular rooms; extract to tea points.</li>
<li>Re-circuit lighting with presence detection; feature lighting under PS2.</li>
<li>Floor boxes to desks and meeting rooms; containment for the client's IT supplier.</li>
<li>Fire alarm detection and sounders adapted to the new room layout.</li></ul>
<h3>How we will run it</h3>
<ul><li>Full-time site manager and a contracts manager visiting twice weekly.</li>
<li>Logistics agreed with building management: goods lift booking, loading bay slots, noisy works before 08:00 and after 18:00 under PS3.</li>
<li>Considerate Constructors registration; weekly progress report to the project manager.</li></ul>
</div>
</div>""")

    rows = [[n, t, money(v, '£')] for n, t, v in WORKS]
    rows += [
        (["", "Measured works subtotal", money(WORKS_SUB, '£')], "sub"),
        (["", "Preliminaries (17 weeks on site plus lead-in; see section 03)", money(PRELIMS, '£')], ""),
        (["", "Overheads and profit (6% on preliminaries and works)", money(OHP, '£')], ""),
        (["", f"Provisional sums (see section 03)", money(PS_SUB, '£')], ""),
        (["", "<b>Tender sum, excluding VAT</b>", f"<b>{money(TENDER, '£')}</b>"], "total"),
        (["", f"Rate per m² NIA ({M2:,} m²)", money(TENDER / M2, '£')], "muted"),
    ]
    d.add(f"""
<div class="kicker">02 · Tender summary</div>
<h2>Tender sum by element</h2>
<p class="lede">Priced against the pricing schedule issued with the tender pack. Illustrative GBP figures. VAT is excluded and charged at the prevailing rate.</p>
{table(["Item", "Element", "Amount"], rows, align=["l","l","r"], widths=["8%","72%","20%"])}
<p class="small">The fully priced pricing schedule is available to the project manager on request.</p>""")

    prelim_rows = [
        ["Site management (site manager full-time, contracts manager part-time)", money(78_400, '£')],
        ["Site set-up, welfare, hoarding and floor protection", money(18_600, '£')],
        ["Waste management and skips (90% diversion from landfill)", money(16_800, '£')],
        ["Goods lift operation, logistics and loading bay management", money(14_200, '£')],
        ["Health and safety, CDM compliance, fire safety during works", money(11_500, '£')],
        ["Insurances (contractor's all risks, employer's and public liability)", money(12_300, '£')],
        ["Final clean, O&amp;M manuals, as-built drawings", money(16_200, '£')],
        (["<b>Preliminaries total</b>", f"<b>{money(PRELIMS, '£')}</b>"], "total"),
    ]
    assert 78_400 + 18_600 + 16_800 + 14_200 + 11_500 + 12_300 + 16_200 == PRELIMS
    ps_rows = [[c, t, money(v, '£')] for c, t, v in PSUMS] + [(["", "<b>Provisional sums total</b>", f"<b>{money(PS_SUB, '£')}</b>"], "total")]
    d.add(f"""
<div class="kicker">03 · Preliminaries and provisional sums</div>
<h2>Preliminaries</h2>
{table(["Item", "Amount"], prelim_rows, align=["l","r"], widths=["80%","20%"])}
<h2 style="margin-top:10px">Provisional sums</h2>
<p class="lede" style="margin-bottom:6px">Included at the values below, inclusive of overheads and profit, and adjusted against actual cost under the contract.</p>
{table(["Ref.", "Description", "Amount"], ps_rows, align=["l","l","r"], widths=["8%","72%","20%"])}""")

    periods = ["Dec", "", "Jan", "", "Feb", "", "Mar", "", "Apr", "", "May", ""]
    sub = ["1–15", "16–31", "1–15", "16–31", "1–14", "15–28", "1–15", "16–31", "1–15", "16–30", "1–15", "16–31"]
    tasks = [
        ("Contract award, licence for alterations, lead-in", 0, 2),
        ("Long-lead orders (glazing, joinery, FCUs)", 1, 4),
        ("Start on site, strip-out, setting out", 3, 3),
        ("Partitions, first-fix M&amp;E", 4, 5),
        ("Glazed partitions, ceilings, second-fix M&amp;E", 6, 7),
        ("Joinery install, decorations, floor finishes", 7, 8),
        ("Testing, commissioning, fire alarm cause and effect", 8, 9),
        ("Snagging, cleaning, handover · PC 14 May", 9, 10),
        ("Client furniture and IT (post-PC)", 10, 10),
    ]
    d.add(f"""
<div class="kicker">04 · Programme</div>
<h2>17 weeks on site to practical completion</h2>
<p class="lede">Lead-in from contract award on 4 December 2026. Start on site 18 January 2027. Practical completion Friday 14 May 2027.</p>
{gantt(periods, tasks, sub=sub)}
<div class="grid3" style="margin-top:8px">
  <div class="card tint"><p style="margin:0"><b>Key dates.</b> Award 4 Dec · licence for alterations 15 Jan · start on site 18 Jan · PC 14 May.</p></div>
  <div class="card tint"><p style="margin:0"><b>Critical path.</b> Glazed partition manufacture (10 weeks) and FCU delivery; ordered on award.</p></div>
  <div class="card tint"><p style="margin:0"><b>Sequence.</b> Level 5 first, then level 4, so the client suite is finished last and snagged clean.</p></div>
</div>""")

    quals = [
        "Our tender is based on the documents listed on the cover. Design development after the tender date is valued as a variation.",
        "The Cat A installation is complete, commissioned and in working order on start on site. Defects in the landlord's works are dealt with under PS4.",
        "Fan coil units are re-used where shown; the number of new units is limited to the 14 shown on the mechanical layouts.",
        "Normal working hours are 08:00–18:00 Monday to Friday. Weekend and out-of-hours work is covered by PS3 only.",
        "The goods lift and loading bay are available for our use for at least 4 hours each working day.",
        "Loose furniture, AV and IT are by the client, installed after practical completion as shown on the programme.",
        "No allowance for asbestos: the building is a recent Cat A shell with a clear refurbishment survey.",
    ]
    excl = ["VAT", "Loose furniture, AV equipment and IT cabling", "Landlord's legal costs and service charge during the works",
            "Planning or building regulations fees beyond PS1", "Works to landlord areas, risers, toilets and the roof",
            "Specialist acoustic testing beyond one test per room type", "Liquidated damages above 5% of the contract sum in total"]
    d.add(f"""
<div class="kicker">05 · Qualifications and exclusions</div>
<h2>Qualifications</h2>
<ol style="padding-left:18px;margin:0 0 6px">{''.join(f'<li style="margin-bottom:5px">{q}</li>' for q in quals)}</ol>
<h2 style="margin-top:8px">Exclusions</h2>
<ul>{''.join(f'<li>{e}</li>' for e in excl)}</ul>""")

    d.add(f"""
<div class="kicker">06 · Tender validity and terms</div>
<h2>Commercial terms</h2>
<ul>
<li><b>Tender validity.</b> 60 days from the return date of 3 November 2026.</li>
<li><b>Contract.</b> JCT Minor Works Building Contract 2016 with the amendments in the tender pack, save for the qualifications in section 05.</li>
<li><b>Payment.</b> Monthly valuations; payment 14 days from the due date. Retention 3%, half released at practical completion and half at the end of the 12-month rectification period.</li>
<li><b>Liquidated damages.</b> Accepted at £2,500 per week, capped at 5% of the contract sum.</li>
<li><b>Insurance.</b> Contractor's all risks to full reinstatement value of the works; employer's liability £10m; public liability £10m.</li>
<li><b>Accreditations.</b> Considerate Constructors registered; site manager SMSTS-trained; all operatives hold CSCS cards.</li>
</ul>
<div class="kicker" style="margin-top:12px">Form of tender</div>
<p>We offer to carry out and complete the works described in the tender documents for the sum of <b>{money(TENDER, '£')}</b> excluding VAT, subject to the qualifications above, and to achieve practical completion by 14 May 2027.</p>
<div class="sig">
  <div><div class="line"></div><div class="lab">For Ashcombe Rook Interiors Ltd · name, position</div><div class="line"></div><div class="lab">Signature · date</div></div>
  <div><div class="line"></div><div class="lab">Accepted for Pellwyn Harcourt LLP · name, position</div><div class="line"></div><div class="lab">Signature · date</div></div>
</div>""")
    return d
