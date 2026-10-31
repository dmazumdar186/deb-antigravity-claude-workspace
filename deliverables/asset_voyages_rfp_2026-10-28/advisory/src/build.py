import markdown, pathlib, sys
v2=len(sys.argv)>1 and sys.argv[1]=='v2'
d=pathlib.Path(__file__).resolve().parent.parent
md="\n".join((d/'src'/f).read_text() for f in (['v2.md'] if v2 else ['part1.md','part2.md','part3.md']))
name='ASSET_Voyages_Advisory_Pack_v2_2026-10-31' if v2 else 'ASSET_Voyages_Technical_Advisory_Pack_2026-10-31'
cssf='style_v2.css' if v2 else 'style.css'
(d/f'{name}.md').write_text(md)
body=markdown.markdown(md,extensions=['tables','fenced_code','toc','md_in_html'],extension_configs={'toc':{'toc_depth':'1-2'}})
css=(d/'src'/cssf).read_text()
html=f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><title>ASSET Voyages Technical Advisory Pack</title><style>{css}</style></head><body>{body}</body></html>'
(d/f'{name}.html').write_text(html)
