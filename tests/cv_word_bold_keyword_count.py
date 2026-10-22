import re, sys, pdfplumber
KW = ["product owner","product manager","product vision","roadmap","user stories","backlog","prioriti","delivery cadence","risk","stakeholder","business partner","needs","expectation","adoption","change management","support materials","use case","roi","ai/ml","vendor","recommendation","responsible ai","explainability","fairness","privacy","compliance","cyber","cross-functional","kpi","governance","documentation","reporting","senior stakeholder","data pipeline","measurable","english","french","healthcare","financial","master","genai","llm","rag","agile","scrum"]
def stats(p):
    with pdfplumber.open(p) as pdf:
        pages=len(pdf.pages); txt="\n".join(pg.extract_text() or "" for pg in pdf.pages)
        bold=sum(1 for pg in pdf.pages for w in pg.extract_words(extra_attrs=["fontname"]) if "Bold" in w["fontname"] and re.search(r"\d",w["text"]))
    t=txt.lower(); hit=[k for k in KW if k in t]; miss=[k for k in KW if k not in t]
    return pages, len(txt.split()), bold, hit, miss
for p in sys.argv[1:]:
    pg,w,b,h,m=stats(p); print(f"\n== {p}\npages={pg} words={w} bold_figures={b} jd_keywords={len(h)}/{len(KW)}\nmissing={m}")
