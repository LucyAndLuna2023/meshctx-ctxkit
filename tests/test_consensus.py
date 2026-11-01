import pytest

from meshctx_ctxkit.consensus import (
    absolute_claim_check,
    arithmetic_check,
    date_check,
    extract_claims,
    percent_check,
    claim_similarity,
    run_offline_checks,
    score_consensus,
)


class TestArithmetic:
    def test_correct_math_passes(self):
        rs = arithmetic_check("The project cost 12 * 30 = 360 hours total.")
        assert rs[0].passed

    def test_wrong_math_fails(self):
        rs = arithmetic_check("Revenue was 250 * 4 = 900 units.")
        assert not rs[0].passed
        assert "360" in rs[0].detail or "computed" in rs[0].detail

    def test_division_and_commas(self):
        rs = arithmetic_check("1,200 / 8 = 150 per week")
        assert rs[0].passed

    def test_word_form(self):
        rs = arithmetic_check("3 plus 4 equals 8, allegedly.")
        assert not rs[0].passed

    def test_percent(self):
        assert percent_check("20% of 150 is 30")[0].passed
        assert not percent_check("20% of 150 is 45")[0].passed


class TestDates:
    def test_impossible_date(self):
        rs = date_check("We shipped on February 30, 2025.")
        assert any(not r.passed for r in rs)

    def test_future_year_flagged(self, monkeypatch):
        rs = date_check("Launch planned for 2099.")
        assert any(not r.passed for r in rs)

    def test_valid_date_ok(self):
        rs = date_check("Released March 14, 2026 to good reviews.")
        assert all(r.passed for r in rs)


class TestAbsolutes:
    def test_flags_marketing_absolutes(self):
        rs = absolute_claim_check("This tool is 100% guaranteed risk-free for everyone.")
        assert not rs[0].passed
        assert "guaranteed" in rs[0].detail

    def test_clean_text(self):
        assert absolute_claim_check("Most users report fewer errors.")[0].passed


class TestOfflineBundle:
    def test_suspicious_text_detected(self):
        text = ("Our 3 agents each handle 50 clients, so 3 * 50 = 180 clients. "
                "It is 100% guaranteed.")
        report = run_offline_checks(text)
        assert report["verdict"] == "suspicious"
        names = {f["name"] for f in report["failed"]}
        assert "arithmetic" in names and "absolute_claims" in names

    def test_clean_text(self):
        report = run_offline_checks("Deploy finished on Monday; logs look normal.")
        assert report["verdict"] == "clean"


class TestConsensusScoring:
    Q = "What is the capital of France?"

    def _answers_agree(self):
        return {
            "m1": "Paris is the capital of France. CLAIMS: [\"Paris is the capital of France\"]",
            "m2": "The capital of France is Paris. CLAIMS: [\"The capital of France is Paris\"]",
            "m3": "France's capital city is Paris. CLAIMS: [\"Paris is France's capital city\"]",
        }

    def _answers_disagree(self):
        return {
            "m1": "CLAIMS: [\"The capital is Lyon\", \"France's capital is Lyon\"]",
            "m2": "CLAIMS: [\"The capital is Marseille\"]",
            "m3": "CLAIMS: [\"The capital is Nice\"]",
        }

    def test_high_agreement(self):
        rep = score_consensus(self.Q, self._answers_agree())
        assert rep.verdict in ("high", "medium")
        assert rep.agreement_score > 0.3
        assert rep.shared_claims, "Paris claim should be shared"

    def test_low_agreement(self):
        rep = score_consensus(self.Q, self._answers_disagree())
        assert rep.verdict == "low"
        assert rep.outlier_claims, "conflicting claims must be listed as outliers"

    def test_single_model_is_error(self):
        rep = score_consensus(self.Q, {"m1": "alone"})
        assert rep.verdict == "error"


class TestClaims:
    def test_extract_json_claims(self):
        ans = 'Paris. CLAIMS: ["claim one here", "claim two here"]'
        assert extract_claims(ans) == ["claim one here", "claim two here"]

    def test_extract_falls_back_to_sentences(self):
        ans = "First sentence about Paris. Second short one. Another full sentence follows!"
        claims = extract_claims(ans)
        assert len(claims) >= 2

    def test_similarity(self):
        assert claim_similarity("the capital of France is Paris",
                                "France capital is Paris") > 0.5
        assert claim_similarity("cats like boxes", "stocks dropped hard") < 0.2
