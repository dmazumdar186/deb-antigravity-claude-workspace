"""
Source provider registry -- RADAR_CONTRACTS.md section A.

`PROVIDERS` / `get_provider(name)` is the single place run.py and the
`--coverage-test` CLI look up a source plugin by name. The three free
chartership-register plugins (engineers_ireland, istructe, ice) register
themselves here at import time.

REGISTRATION HOOK for the licensed-provider build (pdl, crustdata, apollo,
owned separately): call `register_provider(YourProvider())` from your own
module, then have run.py's provider wiring `import` that module once (or add
it below, once it exists) so registration actually runs. This file
deliberately does NOT import sources.pdl / sources.crustdata / sources.apollo
-- that build lands independently and may not exist yet when this module is
imported, and importing a module that doesn't exist yet would break every
test that imports sources.registry.
"""

from __future__ import annotations

from .base import SourceProvider
from .engineers_ireland import EngineersIrelandProvider
from .ice import ICEProvider
from .istructe import IStructEProvider

PROVIDERS: dict[str, SourceProvider] = {}


def register_provider(provider: SourceProvider) -> None:
    """Add (or replace) a provider instance in the registry, keyed by its
    `.name`. The registration hook licensed providers (pdl/crustdata/apollo)
    are expected to call from their own module."""
    PROVIDERS[provider.name] = provider


def get_provider(name: str) -> SourceProvider:
    try:
        return PROVIDERS[name]
    except KeyError:
        raise KeyError(
            f"no source provider registered as {name!r}; registered: {sorted(PROVIDERS)}"
        ) from None


register_provider(EngineersIrelandProvider())
register_provider(IStructEProvider())
register_provider(ICEProvider())

# Licensed providers (pdl, crustdata, apollo) register themselves here --
# see this module's docstring for the hook. Nothing else to add until that
# build lands.
