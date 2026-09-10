"""execution — deterministic-script layer of the workspace (see CLAUDE.md).

This package marker exists so `execution.*` sub-packages (e.g.
`execution.personal_workflows.prodcraft_medspa`) can be imported with
absolute dotted paths, per CONTRACTS.md: "every script is runnable as
`python3 -m execution.personal_workflows.prodcraft_medspa.<pkg>.<script>`".
"""
