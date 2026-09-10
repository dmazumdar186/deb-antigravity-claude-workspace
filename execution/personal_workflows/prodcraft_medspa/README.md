# prodcraft_medspa

ProdCraft "0.5 Website" med-spa lead-gen pipeline. See:

- **Directive (steps, edge cases, self-healing log):** `directives/personal_workflows/prodcraft_medspa_pipeline.md`
- **Build contracts (layout, store interface, `business.json`, scoring rubric, state machine):** `CONTRACTS.md`
- **Project spec (why, phases, offer, economics):** `PROJECT_SPEC.md`
- **Panel pass (design decisions + Honest gaps):** `docs/audits/prodcraft_medspa_panel_pass_2026-09-10.md`

Orchestrator entry points: `scripts/run_metro.py` (discovery -> audit -> enrich -> preview for one
metro), `scripts/daily.py` (the operator's morning command), `scripts/doctor.py` (env/secrets
health check), `scripts/fit_weights.py`, `scripts/sync_sheets.py`.
