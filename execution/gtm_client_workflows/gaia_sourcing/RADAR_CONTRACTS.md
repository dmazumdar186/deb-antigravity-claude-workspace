# Radar build contracts (2026-09-10)

Interface specs for the components being built in parallel for the Monday
14 Sep delivery. Every builder implements exactly the signatures here; the
verifier checks them mechanically. Read HANDOFF.md §5 (invariants I1–I9) and
`radar_final_spec.md` under deliverables/gaia_2026-09-10 for the why.

Rules for every component
- Deterministic Python decides; an LLM may only propose (I3). No LLM call in
  gates, identity, ICP check, opt-out, approval, scorecard.
- All HTTP goes through `core/cache.py` (`fetch`, `fetch_raw`, `fetch_rendered`,
  `head_ok`) or `core/providers.call_role`. `grep -rn "requests\.\(get\|post\)"`
  over layers/ sources/ integrations/ eval/ must show nothing new.
- Every external call is metered: providers report `cost_eur` and the run's
  cost tracker (`core/providers`) or a per-source meter records it.
- Secrets via `core.config.secret(NAME, required=False)`; never logged.
- Tests: no network. Fixture-first: a recorded response per provider under
  `tests/fixtures/<provider>/`, contract tests assert the mapping.
- New stage functions register in `run.py`'s `STAGES` dict; new CLI flags follow
  the existing argparse style. Every write to disk goes under
  `run/<campaign_id>/` (stage JSON) or `logs/` (JSONL).

## A. Source providers — `sources/base.py`
```python
class SourceProvider(Protocol):
    name: str                      # "engineers_ireland", "pdl", ...
    text_source: Literal["text_layer", "ocr", "provider_field"]
    rate_limit_s: float
    def fetch(self, query: SourceQuery) -> SourceResult: ...
    def cost_eur(self, result: SourceResult) -> float: ...

class SourceQuery(BaseModel):     # core/contracts.py
    role_id: str
    niche: str                     # "structural" | "transport" | ...
    terms: list[str]               # e.g. ["chartered engineer", "structural"]
    locations: list[str]           # ROI counties/cities
    limit: int = 100
    cursor: Optional[str] = None

class SourceResult(BaseModel):
    provider: str
    documents: list[RawDocument]   # one per person/page; content_text = the
                                   # exact text the quote validator will see
    provider_records: list[ProviderRecord] = []   # structured fields, licensed data
    next_cursor: Optional[str] = None
    cost_eur: float = 0.0
    fetched: int = 0

class ProviderRecord(BaseModel):  # licensed data only
    provider: str
    external_id: str
    full_name: str
    current_title: Optional[str]
    current_employer: Optional[str]
    city: Optional[str]; region: Optional[str]; country: Optional[str]
    job_history: list[JobStint] = []   # JobStint(title, employer, start: Optional[date], end: Optional[date])
    skills: list[str] = []
    linkedin_url: Optional[str]
    fetched_at: date
    raw_hash: str                  # sha256 of the provider JSON, for audit
```
Registry: `sources/registry.py` → `PROVIDERS: dict[str, SourceProvider]`,
`get_provider(name)`. A licensed record becomes claims with
`confidence="direct"`, `source_url` = the provider record URL or a
`provider://pdl/<id>` URI, `evidence_quote` = the provider field rendered as
`"<field>: <value>"`, and the claim is tagged `text_source="provider_field"`
so it can never be the sole basis of a Tier A primary-signal claim.
Coverage test CLI: `run.py --coverage-test <provider> --niche structural`
prints matched / with title / with employer / with dates / with city, and the
cost; go/no-go threshold 40 matched with title+employer+dates per niche.

## B. Identity resolution — `layers/identity.py`
```python
class RawPersonRecord(BaseModel):
    source: str; source_ref: str
    full_name: str
    employer: Optional[str]; title: Optional[str]; location: Optional[str]
    register_number: Optional[str]; linkedin_url: Optional[str]; email: Optional[str]
    doc_ids: list[str] = []

class PersonCluster(BaseModel):
    person_id: str                 # deterministic slug of canonical name + employer token
    members: list[RawPersonRecord]
    basis: list[str]               # e.g. ["linkedin_url", "name+employer"]
    confidence: Literal["exact", "strong", "weak"]

def resolve_identity(records: list[RawPersonRecord]) -> list[PersonCluster]: ...
```
Pure function, no I/O. Merge rules in priority order: same linkedin_url or
register_number or email → exact; normalised name (fadas stripped, Ó/O'/O
variants, Mc/Mac) + same employer token → strong; same normalised name +
same county with no employer → weak (kept separate unless a later exact key
joins them). Never merge two records with different register numbers or
different linkedin_urls. Fixture suite `tests/fixtures/identity/*.json` with
known collisions (same name/different firm; same firm/different person;
Seán Ó Ríordáin vs Sean O Riordain; initials).

## C. Gate additions — `layers/gates.py`
- `extract_years` callers: a years figure counts only if the sentence's
  subject is the person (pronoun I/my/he/she/name within the same sentence,
  or the claim assertion names the person); a firm sentence ("the practice
  has 40 years...") never passes. Add `_years_subject_is_person(quote, person) -> bool`.
- Seniority floor with `allow_grade_inference=True` gains param
  `require_corroboration: bool = False`; when True, a title-only grade needs
  either a years claim or a second independent source (different doc_id) with
  a matching grade before it passes; otherwise pass_with_note "grade from one
  title only; confirm".
- Both are opt-in params; existing behaviour unchanged when absent.

## D. ICP sample check — `layers/icp_check.py`
```python
class IcpSample(BaseModel): person_id: str; passed: bool; failed_gates: list[str]
class IcpVerdict(BaseModel):
    batch_id: str; sampled: int; matched: int; threshold: int
    verdict: Literal["PASS", "RETRY"]; filter_delta: str; samples: list[IcpSample]
def icp_check(batch_persons: list[str], evaluations: dict[str, Evaluation], sample_n: int = 20, min_match: int = 15, seed: int = 0) -> IcpVerdict
```
Deterministic sampling (seeded), judged with the existing gate results.
`filter_delta` is a suggestion string derived from the most common failed
gate (e.g. "tighten discipline terms: 9/20 failed discipline"). Logged one
line per round: `round N: sampled 20, matched M/20, verdict X, filter delta: ...`.

## E. Outreach safety — `layers/optout.py`, `layers/outreach_queue.py`
- Opt-out registry: `logs/optout.jsonl` (person_id, email, linkedin_url,
  reason, at, source). `is_opted_out(person, contact) -> Optional[OptOut]`
  keyed on any of the three identifiers. Checked at draft creation and at
  sync; a hit blocks and logs.
- Approval state machine per draft:
  `draft -> pending_approval -> approved -> marked_sent | rejected`, stored
  in `run/<campaign>/outreach_queue.json`. Transitions only via
  `approve(draft_id, by: str)`, `reject(draft_id, by, reason)`,
  `mark_sent(draft_id, by, channel)`; each transition appends to
  `logs/outreach_audit.jsonl` with timestamp and user. Nothing in the
  package ever sends; `mark_sent` records what a consultant did.
- Stale evidence: `ContactRecord` gains `evidence_age_days: Optional[int]`
  and `stale: bool` (age > CONFIG.max_evidence_age_days, default 30); the
  contact stage sets it from the newest employer-dimension doc's fetched_at;
  a stale record is delivered with the flag and blocked from CRM sync unless
  `--allow-stale`.
- Error channel: `core/alerts.py` → `alert(service, environment, error, count)`
  posting the fixed shape to `ALERT_WEBHOOK_URL` (Slack or WhatsApp-compatible
  webhook) via `core/cache`-level HTTP (a small `post_json` helper in
  `core/cache.py` is acceptable); `run.py --alert-test` sends one sample.

## F. Evaluation — `eval/`
- `eval/labels.py`: `Label(person_id, grade, location_country, chartered: Literal["yes","no","unknown"], labeller, at, notes)`;
  `eval/labels.jsonl` per campaign; two labellers per person for the
  agreement subset; `cohen_kappa(labels_a, labels_b)` implemented in pure
  Python.
- `eval/blind_label_prompt.md`: a labelling prompt that sees ONLY the source
  text of a document, never the extractor's output, and returns the Label
  fields; used by a Sonnet worker on the operator's machine.
- `eval/scorecard.py` + stage `scorecard`: computes the six numbers from
  `gate.json`, `validate.json`, `poolmap.json`, cost tracker and labels:
  composition_violations, quote_drop_rate, grade_precision,
  residence_precision, delivered_over_pool, cost_per_delivered_card; writes
  `run/<campaign>/scorecard.json` and prints a table. Ship threshold
  constants: violations == 0, grade_precision >= 0.90.
- `eval/outcomes.py`: `record_outcome(person_id, template_id, movability_bucket, event: Literal["draft","approved","sent","reply","conversation","interview","placement","opt_out"], at, by)`
  → `logs/outcomes.jsonl`; `weekly_report()` → reply and conversation rate
  per template_id and per movability_bucket; `template_weights()` returns
  rotation weights (min 0.1, never zero, never rewrites a template).

## G. Console + live re-cut (built after A–F land)
- `render/console.py`: static generator reading `run/<campaign>/*.json` →
  `deliverables/<campaign>/console/` pages: today, jobs, shortlist, card,
  poolmap, scorecard; badges LIVE/CACHED/STUB; health banner from
  `run/<campaign>/health.json`.
- Modal endpoint `execution/modal_radar.py`: `POST /recut {campaign_id, role_id, brief_overrides}`
  → reads cached `extract.json`/`validate.json`, runs the gate layer in memory
  with overrides, writes `run/<campaign>/recuts/<uuid>.json`, returns the
  shortlist. Never touches stage files, never takes the run lock.
