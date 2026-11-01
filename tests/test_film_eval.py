"""Offline unit tests for execution/video/film_eval.py (no ffmpeg, no network).

Run: python3 -m unittest tests.test_film_eval -v   (also collected by pytest)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.video import film_eval as fe

FACTS_MD = """
| id | Fact | Value | Source |
|---|---|---|---|
| F02 | Rows in the file vs members announced | 525 rows, 500 members | x |
| F03 | Duplicate persons | 25 (M0501–M0525) | x |
| F09 | Full logic | 49 | x |
| F13 | Profiles untouched for 2+ years | 68 % | x |
| F14 | No login for 12+ months | 77 % (89 % if the 60 future-dated logins are treated as unknown) | x |
| F18 | Verbatim quote (proof) | "'Roughly' does not pass a board." | x |
| F30 | Big number | 12,500 members | x |
"""


def canons(text: str) -> list[str]:
    return [n.canon for n in fe.extract_numbers(text)]


class NumberExtraction(unittest.TestCase):
    def test_integers_decimals_percent(self):
        self.assertEqual(canons("49 members, 3.5 points, 68 % and 77%"), ["49", "3.5", "68%", "77%"])

    def test_percent_words_and_thousands(self):
        self.assertEqual(canons("89 percent of 12,500 and 1 000"), ["89%", "12500", "1000"])

    def test_ranges_and_record_ids(self):
        self.assertEqual(canons("records M0501–M0525 and 25-30"), ["M0501-M0525", "25-30"])
        self.assertEqual(canons("stub M0502"), ["M0502"])

    def test_no_numbers_inside_words_or_resolutions(self):
        self.assertEqual(canons("v1.2 at 1920x1080 in mp4"), [])

    def test_structural_numbers_stripped_from_script(self):
        line = "## Scene 3 (0:20–0:30) 6 s at 30 fps [F07] `clip_2.mp4` 2026-10-12"
        self.assertEqual(canons(fe.strip_structural(line)), [])
        self.assertEqual(canons(fe.strip_structural("VO: the answer is 49. [F09]")), ["49"])

    def test_tag_forms(self):
        self.assertEqual(fe.extract_tags("x [F07] y (F08, F9) z F10–F12"),
                         ["F07", "F08", "F09", "F10", "F11", "F12"])
        self.assertEqual(fe.strip_tags("answer [F09] (F01, F02)").split(), ["answer"])


class FactMatching(unittest.TestCase):
    def setUp(self):
        self.facts = fe.parse_facts(FACTS_MD)
        self.idx = fe.FactIndex(self.facts)

    def match(self, text: str) -> list[list[str]]:
        return [self.idx.match(n) for n in fe.extract_numbers(text)]

    def test_parse(self):
        self.assertEqual(len(self.facts), 7)
        self.assertEqual(self.facts["F18"].quotes, ["'Roughly' does not pass a board."])

    def test_percent_spacing_tolerated(self):
        self.assertEqual(self.match("68%"), [["F13"]])
        self.assertEqual(self.match("68 %"), [["F13"]])
        self.assertEqual(self.match("89 percent"), [["F14"]])

    def test_percent_kind_must_match(self):
        self.assertEqual(self.match("68 members"), [[]])

    def test_thousands_separator(self):
        self.assertEqual(self.match("12\u202f500"), [["F30"]])  # narrow no-break space
        self.assertEqual(len(self.match("12 500")), 2)            # plain space is not a separator
        self.assertEqual(self.match("12,500"), [["F30"]])

    def test_numbers_from_fact_column(self):
        self.assertEqual(self.match("12+ months"), [["F14"]])

    def test_ranges_and_ids_in_range(self):
        self.assertEqual(self.match("M0501–M0525"), [["F03"]])
        self.assertEqual(self.match("M0502"), [["F03"]])
        self.assertEqual(self.match("M0526"), [[]])

    def test_unmatched_number_fails_with_line(self):
        m, _ = fe.number_fidelity("SRT", [(1, "only 50 members"), (2, "525 rows")], self.idx)
        self.assertEqual(m.verdict, fe.FAIL)
        self.assertEqual(len(m.detail), 1)
        self.assertIn("SRT:1", m.detail[0])

    def test_quote_fidelity_smart_quotes_ok_misquote_fails(self):
        ok = fe.quote_fidelity([("S", 1, "He said “‘Roughly’ does not pass a board.”")], self.facts)
        self.assertEqual(ok.verdict, fe.PASS)
        bad = fe.quote_fidelity([("S", 1, "He said \"'Roughly' does not pass the board.\"")], self.facts)
        self.assertEqual(bad.verdict, fe.FAIL)


class Captions(unittest.TestCase):
    SRT = "﻿1\r\n00:00:01,000 --> 00:00:03,000\r\n<i>Hello</i> world\r\n\r\n2\r\n00:00:03,000 --> 00:00:04,000\r\nabcdefghijklmnopqrstu\r\n"

    def test_parse_and_cps(self):
        cues = fe.parse_srt(self.SRT)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0].lines, ["Hello world"])
        self.assertAlmostEqual(fe.cue_cps(cues[0]), 11 / 2.0)
        self.assertAlmostEqual(fe.cue_cps(cues[1]), 21.0)

    def test_cps_verdicts(self):
        def verdict(chars: int, secs: float) -> str:
            cue = fe.Cue(1, 0.0, secs, ["x" * chars])
            return next(m for m in fe.caption_metrics([cue], 10.0) if m.name == "caption_cps").verdict
        self.assertEqual(verdict(34, 2.0), fe.PASS)   # 17 cps
        self.assertEqual(verdict(40, 2.0), fe.WARN)   # 20 cps
        self.assertEqual(verdict(44, 2.0), fe.FAIL)   # 22 cps

    def test_overlap_fails(self):
        cues = [fe.Cue(1, 0.0, 2.0, ["a"]), fe.Cue(2, 1.5, 3.0, ["b"])]
        timing = next(m for m in fe.caption_metrics(cues, 10.0) if m.name == "caption_timing")
        self.assertEqual(timing.verdict, fe.FAIL)


class WerNormalisation(unittest.TestCase):
    def test_numbers_both_ways(self):
        self.assertEqual(fe.normalize_for_wer("Forty-nine"), fe.normalize_for_wer("49"))
        self.assertEqual(fe.normalize_for_wer("one hundred and twelve days"), fe.normalize_for_wer("112 days"))
        self.assertEqual(fe.normalize_for_wer("68 %"), fe.normalize_for_wer("sixty-eight percent"))
        self.assertEqual(fe.normalize_for_wer("12,500"), ["twelve", "thousand", "five", "hundred"])

    def test_case_punctuation_quotes(self):
        self.assertEqual(fe.normalize_for_wer("“Roughly” doesn’t PASS!"), ["roughly", "doesnt", "pass"])

    def test_ranges_and_ids(self):
        self.assertEqual(fe.normalize_for_wer("M0501–M0525"), fe.normalize_for_wer("m0501 to m0525"))

    def test_wer(self):
        wer, edits, n = fe.word_error_rate(["a", "b", "c", "d"], ["a", "x", "c"])
        self.assertEqual((edits, n), (2, 4))
        self.assertAlmostEqual(wer, 0.5)
        self.assertTrue(fe.contains_seq(fe.normalize_for_wer("we found forty nine"), fe.normalize_for_wer("49")))


class PiiScan(unittest.TestCase):
    def test_email_phone_names(self):
        deny = fe.load_deny(fe.DEFAULT_DENY_NAMES, None)
        self.assertEqual(deny, ["Camille", "Roux"])
        hits = fe.pii_scan([("SRT", 1, "Write to jane.doe@example.org or call +33 6 12 34 56 78"),
                            ("SRT", 2, "camille said so"),
                            ("SRT", 3, "Mme ROUX left")], deny)
        kinds = " ".join(hits)
        self.assertIn("email", kinds)
        self.assertIn("phone", kinds)
        self.assertIn("'Camille'", kinds)
        self.assertIn("'Roux'", kinds)
        self.assertNotIn("jane.doe@example.org", kinds)   # masked

    def test_no_false_positives_on_facts(self):
        clean = [("SRT", 1, "525 rows, 500 members; records M0501–M0525; 1 current + 5 to confirm"),
                 ("SRT", 2, "reference date 2026-10-12, 8 of 12, Camilles"),
                 ("SRT", 3, "Rouxville and e-mail")]
        self.assertEqual(fe.pii_scan(clean, ["Camille", "Roux"]), [])


class NarrationAndExit(unittest.TestCase):
    def test_labelled_narration(self):
        script = "# T\n\n## Scene 1\nON SCREEN: title\nVO: Hello there. [F01]\n**Narrator:** Second line.\n"
        lines, mode = fe.extract_narration(script)
        self.assertEqual(mode, "labelled")
        self.assertEqual([t for _, t in lines], ["Hello there.", "Second line."])

    def test_table_narration(self):
        script = "| # | Time | VO | Facts |\n|---|---|---|---|\n| 1 | 0:00 | We found 49. | F09 |\n"
        lines, mode = fe.extract_narration(script)
        self.assertEqual((mode, [t for _, t in lines]), ("table_column", ["We found 49."]))
        content = [sl.content for sl in fe.parse_script(script)]
        self.assertEqual([canons(c) for c in content], [["49"]])

    def test_missing_input_is_usage_error(self):
        self.assertEqual(fe.main(["--video", "/nope.mp4", "--srt", "/nope.srt", "--script", "/nope.md",
                                  "--facts", "/nope.md"]), 2)


if __name__ == "__main__":
    unittest.main()
