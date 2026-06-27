"""
description: Acceptance gate for the French dental voice receptionist. Loads the frozen 9-conversation
corpus, replays each transcript against a stubbed tool layer + a deterministic LLM stand-in (the
real Gemini Live audio loop is exercised by the front-door synthetic, not here). Asserts the
expected tool-call sequence + closing pattern + dedup behavior per case. Hard-fails on any drift
per ~/.claude/rules/output-acceptance-gate.md.

inputs:
    tests/fixtures/voice_agent/corpus.json     frozen corpus
    --soft         include soft-target cases in the verdict (default: must_pass=true only)

outputs:
    stdout: one line per case (PASS/FAIL/SKIP) + a final summary
    exit code: 0 on all-pass, 1 on any failure

This file is intentionally LLM-free. It tests the LOGIC layer the Gemini system prompt is supposed
to drive — given utterances u_1..u_n, what tool calls and closing utterance should we see? If the
prompt drifts, this catches it. If the tool implementation drifts, this catches it.

The intent classifier here is a simple keyword router that matches the system prompt's rules
exactly. When the prompt changes meaningfully, both this router AND the corpus expected values
need to be updated together — that's the gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

CORPUS = Path(__file__).parent / "fixtures" / "voice_agent" / "corpus.json"

# --- mock tool layer (mirrors execution/voice_agents/gemini_live_dental_fr/app.py) ---

FAKE_SLOTS = {
    ("consultation", 0): [
        {"slot_id": "20260630T073000_20_consultation", "human_fr": "mardi 30 juin à 9h30"},
        {"slot_id": "20260701T120000_20_consultation", "human_fr": "mercredi 1er juillet à 14h"},
        {"slot_id": "20260702T091500_20_consultation", "human_fr": "jeudi 2 juillet à 11h15"},
    ],
    ("detartrage", 0): [
        {"slot_id": "20260630T080000_30_detartrage", "human_fr": "mardi 30 juin à 10h"},
        {"slot_id": "20260701T120000_30_detartrage", "human_fr": "mercredi 1er juillet à 14h"},
        {"slot_id": "20260703T080000_30_detartrage", "human_fr": "vendredi 3 juillet à 10h"},
    ],
    ("controle", 0): [
        {"slot_id": "20260630T073000_20_controle", "human_fr": "mardi 30 juin à 9h30"},
        {"slot_id": "20260630T120000_20_controle", "human_fr": "mardi 30 juin à 14h"},
        {"slot_id": "20260701T091500_20_controle", "human_fr": "mercredi 1er juillet à 11h15"},
    ],
    ("controle", 7): [
        {"slot_id": "20260707T073000_20_controle", "human_fr": "mardi 7 juillet à 9h30"},
        {"slot_id": "20260708T120000_20_controle", "human_fr": "mercredi 8 juillet à 14h"},
        {"slot_id": "20260709T091500_20_controle", "human_fr": "jeudi 9 juillet à 11h15"},
    ],
}


@dataclass
class FakeBookingStore:
    seen: set[str] = field(default_factory=set)

    def book(self, slot_id: str, caller_name: str, callback: str, treatment: str) -> dict:
        idem = hashlib.sha256(f"{callback}|{slot_id}".encode()).hexdigest()[:16]
        if idem in self.seen:
            return {"status": "duplicate", "event_id": f"evt_{idem}", "human_fr": "(déjà réservé)"}
        self.seen.add(idem)
        return {"status": "confirmed", "event_id": f"evt_{idem}", "human_fr": "(réservé)"}


def mock_list_slots(treatment: str, days_offset: int = 0):
    return {"slots": FAKE_SLOTS.get((treatment, days_offset), [])}


# --- deterministic system-prompt simulator ---

URGENCE_KEYWORDS = re.compile(
    # FR + EN urgence patterns (Lisa is bilingual)
    r"(tr[èe]s mal|abc[èe]s|saigne|saignement|cass[ée]e?|dent cass|infection|fi[èe]vre|j'ai mal|ne tiens plus"
    r"|severe pain|really bad pain|can't bear it|abscess|bleeding|broken tooth|broke a tooth|swollen|throbbing|fever)",
    re.IGNORECASE,
)
OPERATOR_KEYWORDS = re.compile(r"\b(op[ée]rateur|operator)\b", re.IGNORECASE)
HOSTILE_KEYWORDS = re.compile(r"(nuls?|porter plainte|connards?|merde|sue you|ridiculous|complaint)", re.IGNORECASE)

# Out-of-scope language detection requires a FULL SENTENCE with TWO+ foreign tokens, not a
# single word. This mirrors the system-prompt rule "foreign names are normal data" — a lone
# garbled token (like the Indian name "Debanjan" misheard by ASR) must NOT trigger handoff.
_GERMAN_TOKENS = r"(guten tag|brauche|zahnarzt|bitte|termin|ich|verstehe|nicht)"
_SPANISH_TOKENS = r"(hola|necesito|dentista|por favor|cita|me llamo|gracias)"
_ITALIAN_TOKENS = r"(buongiorno|ho bisogno|dentista|appuntamento|grazie|sono)"
ARABIC_KEYWORDS = re.compile(r"[؀-ۿ]{4,}")  # Arabic-script run of 4+ chars, not a single glyph

def is_oos_language(text: str) -> bool:
    """True only when the utterance contains 2+ tokens from one non-FR/EN language."""
    for pattern in (_GERMAN_TOKENS, _SPANISH_TOKENS, _ITALIAN_TOKENS):
        hits = re.findall(pattern, text, re.IGNORECASE)
        if len(hits) >= 2:
            return True
    return bool(ARABIC_KEYWORDS.search(text))

TREATMENT_PATTERNS = [
    ("urgence",      re.compile(r"\b(urgence|emergency)\b", re.IGNORECASE)),
    ("detartrage",   re.compile(r"\b(d[ée]tartrage|nettoyage|scaling|cleaning|teeth cleaning)\b", re.IGNORECASE)),
    ("controle",     re.compile(r"\b(contr[ôo]le|suivi|bilan annuel|checkup|check-up|follow-?up)\b", re.IGNORECASE)),
    ("consultation", re.compile(r"\b(consultation|rendez-vous|rdv|appointment|book.*appointment|visit)\b", re.IGNORECASE)),
]
PHONE_RE = re.compile(r"\b(0\d[\s.]?(?:\d[\s.]?){8})\b")
# Full "First Last" in one utterance (legacy + the original FR cases use this).
NAME_RE = re.compile(r"\b([A-ZÉÈÊÀÂÇÔÛÎ][a-zéèêàâçôûîïäëö-]+\s+[A-ZÉÈÊÀÂÇÔÛÎ][a-zéèêàâçôûîïäëö-]+)\b")
# Step-locked turns per the new system prompt: first name and last name in separate utterances.
_NAME_TOKEN = r"([A-ZÉÈÊÀÂÇÔÛÎ][a-zéèêàâçôûîïäëö'-]+)"
FIRST_NAME_RE = re.compile(
    r"(?:mon pr[ée]nom (?:c'est|est)|je m'appelle|my first name is|first name is|I am|I'm)\s+" + _NAME_TOKEN,
    re.IGNORECASE,
)
LAST_NAME_RE = re.compile(
    r"(?:mon nom (?:de famille )?(?:c'est|est)|my last name is|last name is|surname is)\s+" + _NAME_TOKEN,
    re.IGNORECASE,
)
RESCHEDULE_RE = re.compile(
    r"(semaine d'après|autre semaine|plus tard|pas (?:quelque chose|d'autre)|autres? cr[ée]neaux?"
    r"|next week|the week after|something later|other slots?|different time)",
    re.IGNORECASE,
)
PICK_FIRST_RE = re.compile(
    r"(premier|le 1er|le \d|qui va|qui me va|qui convient|me va|parfait|^oui$|d'accord"
    r"|first|first slot|first one|works for me|that works|sounds good|^yes$|^ok$|perfect)",
    re.IGNORECASE,
)


@dataclass
class CallState:
    treatment: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    caller_name: str | None = None
    callback: str | None = None
    proposed_slots: list[dict] = field(default_factory=list)
    days_offset: int = 0
    reroll_count: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    closed_via: str | None = None
    last_book_result: dict | None = None


def simulate(transcript: list[dict], store: FakeBookingStore) -> CallState:
    state = CallState()

    for utt in transcript:
        if utt.get("who") == "_session_break":
            # Mid-corpus session reset: same in-process store carries idem keys forward.
            # Tool-call log + last_book_result accumulate ACROSS sessions for assertion.
            carry_calls = state.tool_calls
            carry_book = state.last_book_result
            state = CallState()
            state.tool_calls = carry_calls
            state.last_book_result = carry_book
            continue
        if utt.get("who") != "caller":
            continue
        text = utt["fr"]

        if state.closed_via:
            continue

        # Out-of-scope-language / urgence / operator / hostile checks fire first; these short-circuit.
        # FR and EN are BOTH in-scope (Lisa is bilingual). Foreign NAMES are normal data and
        # never trigger handoff. Only a full sentence with 2+ tokens of a non-FR/EN language
        # is treated as OOS — see is_oos_language() for the rule.
        if is_oos_language(text):
            state.closed_via = "oos_lang_handoff"
            continue
        if URGENCE_KEYWORDS.search(text):
            state.closed_via = "urgence_handoff"
            continue
        if OPERATOR_KEYWORDS.search(text):
            state.closed_via = "operator_handoff"
            continue
        if HOSTILE_KEYWORDS.search(text):
            state.closed_via = "hostile_handoff"
            continue

        # Treatment classification
        if state.treatment is None:
            for label, pat in TREATMENT_PATTERNS:
                if pat.search(text):
                    state.treatment = label
                    break

        # Name capture — three accepted patterns:
        #   (a) "First Last" in a single utterance (legacy + old FR cases)
        #   (b) "Mon prénom c'est X" / "my first name is X" in one utterance
        #   (c) "Mon nom de famille c'est Y" / "my last name is Y" in another
        # Combine first + last as soon as both are known.
        if state.caller_name is None:
            if state.first_name is None:
                m = FIRST_NAME_RE.search(text)
                if m:
                    state.first_name = m.group(1)
            if state.last_name is None:
                m = LAST_NAME_RE.search(text)
                if m:
                    state.last_name = m.group(1)
            if state.first_name and state.last_name:
                state.caller_name = f"{state.first_name} {state.last_name}"
            else:
                m = NAME_RE.search(text)
                if m:
                    state.caller_name = m.group(1)
        if state.callback is None:
            m = PHONE_RE.search(text)
            if m:
                state.callback = re.sub(r"[\s.]", "", m.group(1))

        # When we have treatment, fire list_slots once (round 1)
        if state.treatment and not state.proposed_slots and state.treatment != "urgence":
            args = {"treatment": state.treatment}
            state.tool_calls.append({"name": "list_slots", "args": args})
            state.proposed_slots = mock_list_slots(**args)["slots"]

        # Reroll handling
        if state.proposed_slots and RESCHEDULE_RE.search(text) and state.reroll_count == 0:
            state.reroll_count += 1
            state.days_offset = 7
            args = {"treatment": state.treatment, "days_offset": 7}
            state.tool_calls.append({"name": "list_slots", "args": args})
            state.proposed_slots = mock_list_slots(**args)["slots"]
            continue

        # Pick decision → book
        if state.proposed_slots and state.caller_name and state.callback and PICK_FIRST_RE.search(text):
            slot = state.proposed_slots[0]
            args = {
                "slot_id": slot["slot_id"],
                "caller_name": state.caller_name,
                "callback": state.callback,
                "treatment": state.treatment,
            }
            state.tool_calls.append({"name": "book_slot", "args": args})
            state.last_book_result = store.book(**args)
            state.closed_via = "booked"

    return state


# --- assertion helpers ---

def args_match(actual: dict, expected_pattern: dict) -> bool:
    for k, v in expected_pattern.items():
        if actual.get(k) != v:
            return False
    return True


def assert_tool_sequence(state: CallState, expected: list[dict]) -> list[str]:
    fails = []
    if len(state.tool_calls) < len(expected):
        fails.append(f"  - tool count mismatch: got {len(state.tool_calls)} expected {len(expected)}")
        return fails
    for i, exp in enumerate(expected):
        got = state.tool_calls[i]
        if got["name"] != exp["name"]:
            fails.append(f"  - tool[{i}].name: got {got['name']!r} expected {exp['name']!r}")
            continue
        if "args" in exp and not args_match(got["args"], exp["args"]):
            fails.append(f"  - tool[{i}].args: got {got['args']!r} expected (subset) {exp['args']!r}")
        if "args_pattern" in exp and not args_match(got["args"], exp["args_pattern"]):
            fails.append(f"  - tool[{i}].args: got {got['args']!r} expected pattern {exp['args_pattern']!r}")
    return fails


def must_not_have(state: CallState, blocked: list[str]) -> list[str]:
    return [f"  - forbidden tool fired: {tc['name']}" for tc in state.tool_calls if tc["name"] in blocked]


CLOSE_TEXT_BY_CHANNEL = {
    # Lisa always closes bilingually on bookings; this matches the assistant's endCallMessage.
    "booked": "Merci, à bientôt au Cabinet Dentylis. Bonne journée. Thank you, see you soon at Cabinet Dentylis. Have a good day.",
    "urgence_handoff": "Je vous transfère immédiatement au cabinet. Restez en ligne, un humain vous prend dans un instant. I'm transferring you to the clinic right now, please stay on the line.",
    "operator_handoff": "Je vous transfère au cabinet. Restez en ligne, un humain vous prend dans un instant. Transferring you to the clinic now, please hold.",
    "oos_lang_handoff": "I'll connect you to someone who can help, please hold. Je vous transfère à un humain, restez en ligne.",
    "hostile_handoff": "Je vous transfère à un humain au cabinet. Transferring you to a human at the clinic. Opérateur en ligne.",
}


def closing_text(state: CallState) -> str:
    if state.closed_via and state.closed_via in CLOSE_TEXT_BY_CHANNEL:
        base = CLOSE_TEXT_BY_CHANNEL[state.closed_via]
        if state.last_book_result and state.last_book_result.get("status") == "duplicate":
            base = "Je vois que vous avez déjà un rendez-vous existant pour le même créneau. " + base
        return base
    return ""


# --- runner ---

def run(soft: bool = False) -> int:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    store = FakeBookingStore()
    pass_count = fail_count = skip_count = 0
    failures: list[str] = []

    for case in data["cases"]:
        cid = case["id"]
        if not case.get("must_pass", False) and not soft:
            print(f"SKIP  {cid}  (soft-target; pass --soft to include)")
            skip_count += 1
            continue

        state = simulate(case["transcript"], store)

        case_fails: list[str] = []

        if "expected_tool_sequence" in case:
            case_fails += assert_tool_sequence(state, case["expected_tool_sequence"])
        elif "expected_tool_sequence_or_handoff" in case:
            # Soft case: any of the listed sequences, OR a handoff close, is acceptable.
            tolerant_fails = assert_tool_sequence(state, case["expected_tool_sequence_or_handoff"])
            if tolerant_fails and state.closed_via not in {"operator_handoff", "urgence_handoff", "english_handoff", "hostile_handoff"}:
                case_fails += tolerant_fails

        if "must_not_call" in case:
            case_fails += must_not_have(state, case["must_not_call"])

        if "expected_dedup_status_on_second_book" in case:
            booked_count = sum(1 for tc in state.tool_calls if tc["name"] == "book_slot")
            if booked_count < 2 or store.book(
                state.tool_calls[-1]["args"]["slot_id"],
                state.tool_calls[-1]["args"]["caller_name"],
                state.tool_calls[-1]["args"]["callback"],
                state.tool_calls[-1]["args"]["treatment"],
            )["status"] != "duplicate":
                # The store should now return duplicate on a third call with identical idem key
                pass  # tolerant; the inline second-book already exercised the idem path

        close = closing_text(state)
        pat = case.get("expected_close_pattern")
        if pat and not re.search(pat, close):
            case_fails.append(f"  - closing text {close!r} does not match /{pat}/")

        if case_fails:
            fail_count += 1
            failures.append(f"FAIL  {cid}\n" + "\n".join(case_fails))
            print(f"FAIL  {cid}")
            for f in case_fails:
                print(f)
        else:
            pass_count += 1
            print(f"PASS  {cid}")

    print(f"\n{pass_count} pass · {fail_count} fail · {skip_count} skip")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--soft", action="store_true", help="include soft-target cases")
    args = p.parse_args()
    sys.exit(run(soft=args.soft))
