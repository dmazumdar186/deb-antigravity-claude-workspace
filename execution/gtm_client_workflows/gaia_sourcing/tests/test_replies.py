"""Tests for layers/replies.py. Zero network: the LLM path is monkeypatched
via core.providers.call_role, never actually invoked unless a test says so.
"""

from __future__ import annotations

import pytest

from gtm_client_workflows.gaia_sourcing.layers import replies


# ---------------------------------------------------------------------------
# Deterministic rules -- one per label
# ---------------------------------------------------------------------------


def test_bounce_is_detected():
    v = replies.classify_reply(
        "This is an automatically generated Delivery Status Notification.\n"
        "Your message was not delivered because the address was not found."
    )
    assert v.label == "bounce"
    assert v.next_action == "human_review"
    assert v.basis == "rule"
    assert v.confidence == "high"
    assert v.opt_out is False


def test_out_of_office_is_detected():
    v = replies.classify_reply("Thanks for your email. I am currently out of office and back Monday.")
    assert v.label == "out_of_office"
    assert v.next_action == "retry_later"
    assert v.basis == "rule"


def test_clear_negative_is_not_interested():
    v = replies.classify_reply("Thanks but not interested, good luck with the search.")
    assert v.label == "not_interested"
    assert v.next_action == "close"
    assert v.opt_out is False


def test_not_now_is_snoozed():
    v = replies.classify_reply("Not the right time for me, maybe circle back in a few months.")
    assert v.label == "not_now"
    assert v.next_action == "snooze_90d"


def test_clear_positive_is_interested():
    v = replies.classify_reply("Sounds interesting, happy to chat -- call me tomorrow.")
    assert v.label == "interested"
    assert v.next_action == "book_call"


def test_a_question_is_routed_to_a_consultant():
    v = replies.classify_reply("What is the salary for this role?")
    assert v.label == "question"
    assert v.next_action == "consultant_answers"


def test_a_bare_trailing_question_mark_counts_as_a_question():
    v = replies.classify_reply("Is this for a permanent position?")
    assert v.label == "question"


# ---------------------------------------------------------------------------
# opt_out MUST be honoured: close + do-not-contact, from "please remove" /
# "unsubscribe" specifically -- not from an ordinary "not interested".
# ---------------------------------------------------------------------------


def test_unsubscribe_sets_opt_out_and_closes():
    v = replies.classify_reply("Please unsubscribe me from any further contact.")
    assert v.opt_out is True
    assert v.label == "not_interested"
    assert v.next_action == "close"


def test_please_remove_sets_opt_out():
    v = replies.classify_reply("Please remove me from your list, thanks.")
    assert v.opt_out is True
    assert v.next_action == "close"


def test_plain_not_interested_does_not_set_opt_out():
    v = replies.classify_reply("Not interested right now, thanks for reaching out.")
    assert v.opt_out is False


def test_crm_note_for_reply_flags_opt_out():
    v = replies.classify_reply("unsubscribe please")
    note = replies.crm_note_for_reply(v, "unsubscribe please")
    assert "OPT-OUT" in note
    assert "do not contact" in note.lower()


def test_crm_note_for_reply_without_opt_out_has_no_opt_out_line():
    v = replies.classify_reply("Not interested, thanks.")
    note = replies.crm_note_for_reply(v, "Not interested, thanks.")
    assert "OPT-OUT" not in note


# ---------------------------------------------------------------------------
# Rule precedence -- bounce/opt-out must win over an incidental question mark
# or out-of-office footer elsewhere in the same message.
# ---------------------------------------------------------------------------


def test_bounce_wins_over_a_trailing_question_mark():
    v = replies.classify_reply("Delivery has failed for the following recipients. Retry?")
    assert v.label == "bounce"


def test_opt_out_wins_over_an_out_of_office_style_footer():
    v = replies.classify_reply(
        "Please unsubscribe me. (Sent from my out of office auto-responder.)"
    )
    assert v.opt_out is True


# ---------------------------------------------------------------------------
# use_llm=False never calls the provider
# ---------------------------------------------------------------------------


def test_use_llm_false_never_calls_the_provider(monkeypatch):
    def explode(*a, **kw):
        raise AssertionError("call_role must not be invoked when use_llm=False")

    monkeypatch.setattr(replies, "call_role", explode)

    v = replies.classify_reply("Interesting, but I need to think about it some more maybe.",
                                use_llm=False)

    assert v.label == "unclear"
    assert v.next_action == "human_review"
    assert v.basis == "rule"
    assert v.confidence == "low"


# ---------------------------------------------------------------------------
# LLM path -- only reached when no rule matched and use_llm=True
# ---------------------------------------------------------------------------


AMBIGUOUS_TEXT = "Interesting, but I need to think about it some more maybe."


def test_llm_path_is_used_only_when_no_rule_matches(monkeypatch):
    calls = []

    def fake_call_role(role, system, user, tool, max_tokens=8000, **kw):
        calls.append(role)
        return (
            {"label": "not_now", "evidence": "think about it", "confidence": "low"},
            {"provider": "fake", "model": "fake"},
        )

    monkeypatch.setattr(replies, "call_role", fake_call_role)

    v = replies.classify_reply(AMBIGUOUS_TEXT)

    assert calls == [replies.ROLE_JUDGE]
    assert v.label == "not_now"
    assert v.next_action == "snooze_90d"
    assert v.basis == "llm"
    assert v.confidence == "low"
    assert v.evidence == "think about it"
    assert v.opt_out is False  # never set on the LLM path


def test_llm_path_is_skipped_when_a_rule_already_matched(monkeypatch):
    def explode(*a, **kw):
        raise AssertionError("call_role must not fire when a rule already matched")

    monkeypatch.setattr(replies, "call_role", explode)

    v = replies.classify_reply("Not interested, thanks.")

    assert v.label == "not_interested"


def test_an_out_of_range_llm_label_falls_back_to_unclear(monkeypatch):
    monkeypatch.setattr(
        replies, "call_role",
        lambda *a, **kw: ({"label": "maybe", "evidence": "hmm", "confidence": "high"}, {}),
    )

    v = replies.classify_reply(AMBIGUOUS_TEXT)

    assert v.label == "unclear"
    assert v.next_action == "human_review"


def test_llm_failure_yields_unclear_and_human_review(monkeypatch):
    def explode(*a, **kw):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(replies, "call_role", explode)

    v = replies.classify_reply(AMBIGUOUS_TEXT)

    assert v.label == "unclear"
    assert v.next_action == "human_review"
    assert v.basis == "llm"
    assert v.confidence == "low"


def test_llm_returning_nothing_usable_yields_unclear(monkeypatch):
    monkeypatch.setattr(replies, "call_role", lambda *a, **kw: (None, {}))

    v = replies.classify_reply(AMBIGUOUS_TEXT)

    assert v.label == "unclear"
    assert v.basis == "llm"


# ---------------------------------------------------------------------------
# next_action mapping is a fixed dict -- deterministic, not model-decided
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label,expected", [
    ("interested", "book_call"),
    ("not_now", "snooze_90d"),
    ("not_interested", "close"),
    ("question", "consultant_answers"),
    ("out_of_office", "retry_later"),
    ("bounce", "human_review"),
    ("unclear", "human_review"),
])
def test_next_action_map_is_exhaustive_and_fixed(label, expected):
    assert replies._NEXT_ACTION[label] == expected
