"""Offline unit tests for execution/video/film_eval.py (no ffmpeg, no network).

Run: python3 -m unittest tests.test_film_eval -v   (also collected by pytest)
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.video import film_eval as fe

GOLDEN = _ROOT / "execution" / "video" / "eval_data" / "golden_v1"

FACTS_MD = """
Reference date 2026-10-12.

| id | Fact | Value | Source |
|---|---|---|---|
| F02 | Rows in the file vs members announced | 525 rows, 500 members | x |
| F03 | Duplicate persons | 25 (M0501–M0525) | x |
| F09 | Full logic | 49 | x |
| F13 | Profiles untouched for 2+ years | 68 % | x |
| F14 | No login for 12+ months | 77 % (89 % if the 60 future-dated logins are treated as unknown) | x |
| F17 | Verbatim quote (truth) | "340 London expats. Twenty had moved back years ago. Two unsubscribed." | x |
| F18 | Verbatim quote (proof) | "'Roughly' does not pass a board." | x |
| F22 | Insight | "Three years in post" and "three years without an update" are the same signal | x |
| F30 | Big number | 12,500 members | x |
"""


def canons(text: str, prefixes: set[str] | None = None) -> list[str]:
    return [n.canon for n in fe.extract_numbers(text, prefixes)]


def index() -> tuple[dict, fe.FactIndex]:
    facts = fe.parse_facts(FACTS_MD)
    return facts, fe.FactIndex(facts, FACTS_MD)


class NumberExtraction(unittest.TestCase):
    def test_integers_decimals_percent(self):
        self.assertEqual(canons("49 members, 3.5 points, 68 % and 77%"), ["49", "3.5", "68%", "77%"])

    def test_percent_words_and_thousands(self):
        self.assertEqual(canons("89 percent of 12,500 and 1\u00a0000"), ["89%", "12500", "1000"])

    def test_ranges_ids_dates(self):
        self.assertEqual(canons("records M0501–M0525 and 25-30"), ["M0501-M0525", "25-30"])
        self.assertEqual(canons("ref. 2026-10-12"), ["2026-10-12"])

    def test_r2_unknown_id_prefix_is_structure(self):
        self.assertEqual(canons("S02 L01 M0502", {"M"}), ["M0502"])

    def test_r3_resolution_bpm_speed_stripped(self):
        line = "76.25 s · 1920×1080 · 24 fps · speed 0.9 · 72 BPM · crf 26 · 1280 x 720"
        self.assertEqual(canons(fe.strip_structural(line)), [])

    def test_structural_numbers_stripped(self):
        line = "## Scene 3 (0:20–0:30) 6 s at 30 fps [F07] `clip_2.mp4`"
        self.assertEqual(canons(fe.strip_structural(line)), [])
        self.assertEqual(canons(fe.strip_structural("VO: the answer is 49. [F09]")), ["49"])

    def test_tag_forms(self):
        self.assertEqual(fe.extract_tags("x [F07] y (F08, F9) z F10–F12"),
                         ["F07", "F08", "F09", "F10", "F11", "F12"])


class WordsToDigits(unittest.TestCase):
    def test_spoken_numbers(self):
        w = fe.words_to_digits
        self.assertEqual(w("forty-nine"), "49")
        self.assertEqual(w("five hundred and twenty-five records"), "525 records")
        self.assertEqual(w("Three hundred and forty London expats"), "340 London expats")
        self.assertEqual(canons(w("sixty-eight per cent")), ["68%"])
        self.assertEqual(w("twenty twenty-six"), "20 26")
        self.assertEqual(w("two thousand and twelve"), "2012")

    def test_lone_one_is_a_word(self):
        self.assertEqual(fe.words_to_digits("One sentence, one user"), "One sentence, one user")
        self.assertEqual(fe.words_to_digits("One current", lone_one=True), "1 current")
        self.assertEqual(fe.spoken_numbers("one current, five to confirm, forty-three"), {"1", "5", "43"})


class FactMatching(unittest.TestCase):
    def setUp(self):
        self.facts, self.idx = index()

    def match(self, text: str) -> list[list[str]]:
        return [self.idx.match(n) for n in fe.extract_numbers(text, self.idx.id_prefixes)]

    def test_parse(self):
        self.assertEqual(len(self.facts), 9)
        self.assertEqual(self.facts["F18"].quotes, ["'Roughly' does not pass a board."])
        self.assertEqual(self.idx.id_prefixes, {"M"})

    def test_percent_spacing_tolerated_and_kind_must_match(self):
        self.assertEqual(self.match("68%"), [["F13"]])
        self.assertEqual(self.match("68 %"), [["F13"]])
        self.assertEqual(self.match("89 percent"), [["F14"]])
        self.assertEqual(self.match("68 members"), [[]])

    def test_thousands_separator(self):
        self.assertEqual(self.match("12 500"), [["F30"]])
        self.assertEqual(self.match("12,500"), [["F30"]])

    def test_r7_number_words_in_facts(self):
        self.assertEqual(self.match("3 yrs"), [["F22"]])
        self.assertIn("F17", self.match("20 had moved")[0])

    def test_ranges_ids_dates(self):
        self.assertEqual(self.match("M0501–M0525"), [["F03"]])
        self.assertEqual(self.match("M0502"), [["F03"]])
        self.assertEqual(self.match("ref. 2026-10-12"), [["FACTS.md"]])
        self.assertEqual(self.match("2026-10-13"), [[]])

    def test_unmatched_number_fails_stub_is_info(self):
        m = fe.number_fidelity("nf", "SRT", [("SRT:1", "only 50 members", fe.extract_numbers("only 50 members")),
                                            ("SRT:2", "card M0475", fe.extract_numbers("card M0475", {"M"}))], self.idx)
        self.assertEqual(m.verdict, fe.FAIL)
        self.assertEqual(m.n, 2)
        self.assertTrue(m.detail[0].startswith("SRT:1"))
        self.assertTrue(m.detail[1].startswith("INFO"))


class Quotes(unittest.TestCase):
    def setUp(self):
        self.facts, _ = index()

    def qf(self, ctx: str, cell: str) -> fe.Metric:
        return fe.quote_fidelity([("L", ctx, [cell])], self.facts, "test")

    def test_smart_quotes_ok_misquote_fails(self):
        self.assertEqual(self.qf("quotation:spoken", "He said “‘Roughly’ does not pass a board.”").verdict, fe.PASS)
        self.assertEqual(self.qf("quotation:spoken", "He said \"'Roughly' does not pass the board.\"").verdict, fe.FAIL)

    def test_r4_smart_pairs_first(self):
        self.assertEqual(fe.extract_quotes('"read as tenure — “Three years in post”"'),
                         ["read as tenure", "Three years in post"])
        self.assertEqual(fe.extract_quotes('Pen stroke "=" and label "the same signal"'), ["the same signal"])

    def test_r5_line_breaks(self):
        cell = "Note: “340 London expats. / Twenty had moved back years ago. / Two unsubscribed.”"
        self.assertEqual(self.qf("quotation:onscreen", cell).verdict, fe.PASS)

    def test_r6_labels_are_info_and_first_letter_case_ok(self):
        m = self.qf("label", 'Reading: "Rows in the file / 525 / for 500 members announced"')
        self.assertEqual(m.verdict, fe.PASS)
        self.assertTrue(m.detail[0].startswith("INFO"))
        self.assertEqual(self.qf("quotation:spoken", "“Three years without an update”").verdict, fe.PASS)
        self.assertEqual(self.qf("label", '"Roughly does not pass the board"').verdict, fe.WARN)


class Script(unittest.TestCase):
    SCRIPT = """# Title
Duration 76 s · 1920×1080 · 24 fps · speed 0.9 · 72 BPM grid.

## Narration

| # | In | Out | Spoken text | Facts |
|---|---|---|---|---|
| L01 | 00:00.42 | 00:05.88 | The file: five hundred and twenty-five records. | F02 |
| L02 | 00:06.00 | 00:08.00 | But look at the dates. | — |

## Subtitles

| Cue | Text | Facts |
|---|---|---|
| S02 | 1920 junk 777 | F02 |

## On-screen text

| In | Out | What is on screen | Facts |
|---|---|---|---|
| 00:09.97 | 00:12.57 | Reading: "Rows in the file / 525" | F02 |

Card IDs (M0001–M0525) are anonymous stubs.
"""

    def test_sections_only_and_footnote_ignored(self):
        srcs, mode = fe.script_sources(self.SCRIPT)
        self.assertEqual(mode, "sections")
        self.assertEqual([(s.kind, s.lineno) for s in srcs], [("narration", 8), ("narration", 9), ("onscreen", 21)])
        self.assertEqual(srcs[0].text, "The file: five hundred and twenty-five records.")
        self.assertEqual([n.canon for n in fe.src_numbers(srcs[0], {"M"})], ["525"])
        self.assertEqual(srcs[0].tags, ["F02"])

    def test_labelled_fallback(self):
        srcs, mode = fe.script_sources("# T\nTarget: 40 s\nON SCREEN: London, 8 ways [F04]\nVO: Hello there. [F01]\n")
        self.assertEqual(mode, "labelled")
        self.assertEqual([(s.kind, s.text) for s in srcs], [("onscreen", "London, 8 ways"), ("narration", "Hello there.")])

    def test_golden_v1_no_false_positives(self):
        ft = (GOLDEN / "FACTS.md").read_text(encoding="utf-8")
        facts = fe.parse_facts(ft)
        idx = fe.FactIndex(facts, ft)
        srcs, mode = fe.script_sources((GOLDEN / "SCRIPT.md").read_text(encoding="utf-8"))
        self.assertEqual(mode, "sections")
        cues = fe.parse_srt((GOLDEN / "trusted-segments.srt").read_text(encoding="utf-8"))
        for kind in ("narration", "onscreen"):
            m = fe.number_fidelity(kind, kind, [(s.loc, s.text, fe.src_numbers(s, idx.id_prefixes))
                                                for s in srcs if s.kind == kind], idx)
            self.assertEqual(m.verdict, fe.PASS, m.detail)
        m = fe.number_fidelity("srt", "srt", [(str(c.index), c.text, fe.extract_numbers(c.text, idx.id_prefixes))
                                              for c in cues], idx)
        self.assertEqual(m.verdict, fe.PASS, m.detail)
        entries = [(s.loc, "quotation:spoken" if s.kind == "narration" else "label", s.cells) for s in srcs]
        entries.append(("SRT", "quotation:spoken", [" ".join(c.text for c in cues)]))
        self.assertNotEqual(fe.quote_fidelity(entries, facts, "g").verdict, fe.FAIL)
        tags = {m.name: m for m in fe.tag_metrics(srcs, facts, idx, "SCRIPT.md")}
        self.assertEqual(tags["tag_coverage"].verdict, fe.PASS, tags["tag_coverage"].detail)

    def test_golden_v1_planted_mutations_caught(self):
        ft = (GOLDEN / "FACTS.md").read_text(encoding="utf-8")
        facts = fe.parse_facts(ft)
        idx = fe.FactIndex(facts, ft)
        script = (GOLDEN / "SCRIPT.md").read_text(encoding="utf-8")
        script = script.replace("job titles: forty-nine.", "job titles: forty-eight.")      # narration
        script = script.replace("Counts land: 1 · 5 · 43", "Counts land: 1 · 5 · 34")        # on-screen
        srcs, _ = fe.script_sources(script)
        bad = {}
        for kind in ("narration", "onscreen"):
            bad[kind] = fe.number_fidelity(kind, kind, [(s.loc, s.text, fe.src_numbers(s, idx.id_prefixes))
                                                        for s in srcs if s.kind == kind], idx)
        self.assertEqual(bad["narration"].verdict, fe.FAIL)
        self.assertIn("48", bad["narration"].detail[0])
        self.assertEqual(bad["onscreen"].verdict, fe.FAIL)


class Captions(unittest.TestCase):
    SRT = "﻿1\r\n00:00:01,000 --> 00:00:03,000\r\n<i>Hello</i> world\r\n\r\n2\r\n00:00:03,000 --> 00:00:04,000\r\nabcdefghijklmnopqrstu\r\n"

    def test_parse_cps_and_speech_time(self):
        cues = fe.parse_srt(self.SRT)
        self.assertEqual(cues[0].lines, ["Hello world"])
        self.assertAlmostEqual(fe.cue_cps(cues[0]), 11 / 2.0)
        self.assertAlmostEqual(fe.cue_cps(cues[1]), 21.0)
        self.assertAlmostEqual(fe.speech_seconds(cues), 3.0)

    def test_cps_verdicts(self):
        def verdict(chars: int, secs: float) -> str:
            cue = fe.Cue(1, 0.0, secs, ["x" * chars])
            return next(m for m in fe.caption_metrics([cue], 10.0, 24.0, "t.srt") if m.name == "caption_cps").verdict
        self.assertEqual(verdict(34, 2.0), fe.PASS)
        self.assertEqual(verdict(40, 2.0), fe.WARN)
        self.assertEqual(verdict(44, 2.0), fe.FAIL)

    def test_gap_is_two_frames_at_video_fps(self):
        cues = [fe.Cue(1, 0.0, 2.0, ["a"]), fe.Cue(2, 2.04, 3.0, ["b"])]
        t24 = next(m for m in fe.caption_metrics(cues, 10.0, 24.0, "t") if m.name == "caption_timing")
        t60 = next(m for m in fe.caption_metrics(cues, 10.0, 60.0, "t") if m.name == "caption_timing")
        self.assertEqual((t24.verdict, t60.verdict), (fe.WARN, fe.PASS))
        over = [fe.Cue(1, 0.0, 2.0, ["a"]), fe.Cue(2, 1.5, 3.0, ["b"])]
        self.assertEqual(next(m for m in fe.caption_metrics(over, 10.0, 24.0, "t")
                              if m.name == "caption_timing").verdict, fe.FAIL)


class Drawn(unittest.TestCase):
    def test_drawn_numbers_size_and_merge(self):
        _, idx = index()
        items = [{"text": "49", "t_start": 1.0, "t_end": 1.04, "x": 10, "y": 10, "px": 96},
                 {"text": "49", "t_start": 1.04, "t_end": 4.0, "x": 10, "y": 10, "px": 96},
                 {"text": "×2.5", "t_start": 2.0, "t_end": 2.5, "x": 50, "y": 10, "px": 40},
                 {"text": "of 500 members", "t_start": 1.0, "t_end": 3.0, "x": 10, "y": 90, "px": 22}]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "drawn_text.json"
            p.write_text(json.dumps(items), encoding="utf-8")
            drawn = fe.load_drawn(p)
        self.assertEqual(len(drawn), 3)
        ms = {m.name: m for m in fe.drawn_metrics(drawn, idx, "drawn_text.json", 1080)}
        self.assertEqual(ms["number_fidelity_drawn"].verdict, fe.FAIL)
        self.assertIn("2.5", " ".join(ms["number_fidelity_drawn"].detail))
        self.assertEqual(ms["drawn_text_size"].verdict, fe.WARN)


class WerNormalisation(unittest.TestCase):
    def test_numbers_both_ways(self):
        self.assertEqual(fe.normalize_for_wer("Forty-nine"), fe.normalize_for_wer("49"))
        self.assertEqual(fe.normalize_for_wer("one hundred and twelve days"), fe.normalize_for_wer("112 days"))
        self.assertEqual(fe.normalize_for_wer("68 %"), fe.normalize_for_wer("sixty-eight percent"))

    def test_case_punctuation_quotes(self):
        self.assertEqual(fe.normalize_for_wer("“Roughly” doesn’t PASS!"), ["roughly", "doesnt", "pass"])

    def test_wer_and_word_count(self):
        wer, edits, n = fe.word_error_rate(["a", "b", "c", "d"], ["a", "x", "c"])
        self.assertEqual((edits, n), (2, 4))
        self.assertAlmostEqual(wer, 0.5)
        self.assertEqual(fe.count_words("Twenty-five people don't appear [F03]."), 4)


class PiiScan(unittest.TestCase):
    def test_email_phone_names(self):
        deny = fe.load_deny(fe.DEFAULT_DENY_NAMES, None)
        self.assertEqual(deny, ["Camille", "Roux"])
        hits = " ".join(fe.pii_scan([("SRT", 1, "Write to jane.doe@example.org or call +33 6 12 34 56 78"),
                                     ("SRT", 2, "camille said so"), ("SRT", 3, "Mme ROUX left")], deny))
        for kind in ("email", "phone", "'Camille'", "'Roux'"):
            self.assertIn(kind, hits)
        self.assertNotIn("jane.doe@example.org", hits)

    def test_no_false_positives_on_facts(self):
        clean = [("SRT", 1, "525 rows, 500 members; records M0501–M0525; 1 current + 5 to confirm"),
                 ("SRT", 2, "reference date 2026-10-12, 8 of 12, Camilles"), ("SRT", 3, "Rouxville and e-mail")]
        self.assertEqual(fe.pii_scan(clean, ["Camille", "Roux"]), [])


class CalibrationAndCompare(unittest.TestCase):
    def test_auroc_and_threshold(self):
        self.assertEqual(fe.auroc([0.9, 0.8], [0.1, 0.2]), 1.0)
        self.assertEqual(fe.auroc([0.5], [0.5]), 0.5)
        b = fe.best_threshold([0.9, 0.8, 0.3, 0.1], [1, 1, 0, 0])
        self.assertEqual((b["tp"], b["fp"], b["fn"], b["tn"]), (2, 0, 0, 2))
        self.assertTrue(0.3 < b["threshold"] <= 0.8)

    def test_calibration_file_is_valid(self):
        cal = fe.load_jev_calibration()
        self.assertTrue(cal, "run --calibrate to create eval_data/jev_support_thresholds.json")
        for q in ("claim", "entailed", "contradiction"):
            self.assertGreaterEqual(cal[q]["auroc"], 0.5)
            self.assertTrue(0.0 <= cal[q]["threshold"] <= 1.0001)

    def test_compare_reports(self):
        old = {"metrics": [{"name": "speech_rate", "value": 122.8, "unit": "wpm", "verdict": "WARN"},
                           {"name": "gone", "value": 1, "verdict": "FAIL"}]}
        new = [fe.Metric("content", "speech_rate", 137.4, "-", fe.PASS, unit="wpm"),
               fe.Metric("technical", "resolution", "1920x1080", "-", fe.PASS)]
        rows = {r["name"]: r for r in fe.compare_reports(old, new)}
        self.assertEqual(rows["speech_rate"]["delta"], "+14.6")
        self.assertEqual(rows["speech_rate"]["verdict"], "WARN -> PASS")
        self.assertEqual(rows["resolution"]["old"], "(new)")
        self.assertEqual(rows["gone"]["new"], "(removed)")

    def test_missing_input_is_usage_error(self):
        self.assertEqual(fe.main(["--video", "/nope.mp4", "--srt", "/nope.srt", "--script", "/nope.md",
                                  "--facts", "/nope.md"]), 2)


if __name__ == "__main__":
    unittest.main()
