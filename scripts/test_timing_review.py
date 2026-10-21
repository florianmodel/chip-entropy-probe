"""Fast parser checks for the tracked routed-timing review runner."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).with_name("timing-review.py")
spec = importlib.util.spec_from_file_location("timing_review", SCRIPT)
timing_review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing_review)


def sample_log():
    pieces = [
        "TIMING_REVIEW_SETUP_BEGIN\n0.500 slack (MET)\nTIMING_REVIEW_SETUP_END",
        "TIMING_REVIEW_HOLD_BEGIN\n0.200 slack (MET)\nTIMING_REVIEW_HOLD_END",
        "TIMING_REVIEW_PULSE_PERIOD_VIOLATIONS_BEGIN\n\nTIMING_REVIEW_PULSE_PERIOD_VIOLATIONS_END",
        "TIMING_REVIEW_MIN_PERIOD_BEGIN\nclk period_min = 2.50 fmax = 400.00\nTIMING_REVIEW_MIN_PERIOD_END",
        "TIMING_REVIEW_PULSE_WIDTH_BEGIN\nPin: probe.divider.stage[0].ff/CLK\n"
        "Check: sequential_clock_pulse_width\nTIMING_REVIEW_PULSE_WIDTH_END",
    ]
    for name in timing_review.expected_coverage_names():
        pieces.append(f"TIMING_REVIEW_COVERAGE_BEGIN_{name}\n"
                      f"Startpoint: {name}/Q\nEndpoint: {name}/D\n"
                      f"TIMING_REVIEW_COVERAGE_END_{name}")
    return "\n".join(pieces)


class TimingReviewParserTests(unittest.TestCase):
    def test_parses_good_corner_and_all_required_path_queries(self):
        result = timing_review.parse_log(sample_log())
        self.assertEqual(result["setup_slacks"], [{"value": 0.5, "status": "MET"}])
        self.assertEqual(result["hold_slacks"], [{"value": 0.2, "status": "MET"}])
        self.assertTrue(all(result["coverage"].values()))
        self.assertFalse(result["pulse_period_violations"])
        self.assertEqual(result["min_period_rows"], [{"clock": "clk", "period_min": 2.5, "fmax_mhz": 400.0}])
        self.assertEqual(result["pulse_width_check_count"], 1)
        self.assertFalse(result["invalid_object_warnings"])
        self.assertFalse(result["opensta_errors"])

    def test_detects_negative_slack_status_and_invalid_sdc_object(self):
        log = sample_log().replace("0.500 slack (MET)", "-0.100 slack (VIOLATED)")
        log += "\nWarning: 'foo/X' is not a valid start point."
        result = timing_review.parse_log(log)
        self.assertEqual(result["setup_slacks"][0]["status"], "VIOLATED")
        self.assertTrue(result["invalid_object_warnings"])

    def test_missing_query_is_not_counted_as_coverage(self):
        log = sample_log().replace("Startpoint: divider_stage_0/Q\nEndpoint: divider_stage_0/D\n", "")
        result = timing_review.parse_log(log)
        self.assertFalse(result["coverage"]["divider_stage_0"])

    def test_empty_diagnostic_sections_and_tool_errors_are_not_reports(self):
        log = sample_log().replace(
            "clk period_min = 2.50 fmax = 400.00\n", "")
        log = log.replace("Pin: probe.divider.stage[0].ff/CLK\nCheck: sequential_clock_pulse_width\n", "")
        log += "\nError: couldn't resolve the report target\n"
        result = timing_review.parse_log(log)
        self.assertFalse(result["min_period_report_present"])
        self.assertFalse(result["pulse_width_report_present"])
        self.assertTrue(result["opensta_errors"])


if __name__ == "__main__":
    unittest.main()
