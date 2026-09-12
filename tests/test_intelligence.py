import unittest

from agent_orchestrator import AgentResult, build_chief_input
from agent_runtime import assess, challenge_agents, debate_agents
from ai_brain import _fallback
from news_intelligence import claim_status, evidence_score, similarity


class NewsIntelligenceTests(unittest.TestCase):
    def test_claim_status_is_conservative(self):
        status, _ = claim_status("UNVERIFIED", [], [])
        self.assertEqual(status, "INSUFFICIENT EVIDENCE")
        status, _ = claim_status("SINGLE_SOURCE", ["Publisher A"], ["POSITIVE"])
        self.assertEqual(status, "INSUFFICIENT EVIDENCE")
        status, _ = claim_status("CROSS_CHECKED", ["Publisher A", "Publisher B"], ["POSITIVE", "POSITIVE"])
        self.assertEqual(status, "SUPPORTED")
        status, _ = claim_status("CONFLICTING", ["Publisher A", "Publisher B"], ["POSITIVE", "NEGATIVE"])
        self.assertEqual(status, "DISPUTED")

    def test_evidence_score_bounds(self):
        self.assertEqual(evidence_score("UNVERIFIED", 0), 10)
        self.assertEqual(evidence_score("SINGLE_SOURCE", 1), 30)
        self.assertLessEqual(evidence_score("CORROBORATED", 4), 100)
        self.assertLessEqual(evidence_score("CROSS_CHECKED", 10), 100)
        self.assertEqual(evidence_score("CONFLICTING", 4), 35)

    def test_headline_similarity_is_reasonable(self):
        self.assertEqual(similarity("Nifty rises after RBI decision", "Nifty rises after RBI decision"), 1.0)
        self.assertGreater(similarity("Nifty rises after RBI decision", "Nifty falls after RBI decision"), 0.2)
        self.assertLess(similarity("Indian bank earnings strong", "European football results"), 0.2)

    def test_chief_input_contains_governance(self):
        packet = build_chief_input({}, [], [], [], [], {}, {"agents": {}})
        self.assertTrue(packet["governance"]["conflicts_must_be_reported"])
        self.assertTrue(packet["governance"]["no_order_execution"])
        self.assertTrue(packet["governance"]["no_fabrication"])

    def test_ai_fallback_is_safe(self):
        result = _fallback({"rule_bias": "NEUTRAL", "decision": {"score": 50, "bias": "NEUTRAL", "confidence": "LOW"}}, "TEST")
        self.assertEqual(result["bias"], "NEUTRAL")
        self.assertEqual(result["decision_score"], 50)
        self.assertEqual(result["evidence_quality"], "INSUFFICIENT")

    def test_agent_result_shape(self):
        result = AgentResult.ok("Test Agent", {"x": 1}, 12.3)
        self.assertEqual(result["agent"], "Test Agent")
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["data"]["x"], 1)

    def test_agent_self_check_flags_missing_evidence(self):
        result = assess("Technical Agent", {"trend_vs_20d": "UNKNOWN", "trend_vs_50d": "UNKNOWN"})
        self.assertEqual(result["evidence_state"], "INSUFFICIENT")
        self.assertTrue(result["needs_retry"])

    def test_agent_challenge_detects_conflict(self):
        results = {
            "Technical Agent": {"data": {"trend_vs_20d": "ABOVE"}},
            "Options Agent": {"data": {"oi_bias": "BEARISH"}},
            "Risk Agent": {"data": {"flags": []}},
        }
        conflicts = challenge_agents(results)
        self.assertTrue(conflicts)
        self.assertIn("Options Agent", conflicts[0]["agents"])

    def test_debate_layer_is_bounded_and_structured(self):
        results = {
            "Technical Agent": {"data": {"trend_vs_20d": "ABOVE"}},
            "Options Agent": {"data": {"oi_bias": "BEARISH"}},
            "Risk Agent": {"data": {"flags": []}},
        }
        debates = debate_agents(results, max_debates=5)
        self.assertEqual(len(debates), 1)
        self.assertEqual(debates[0]["severity"], "HIGH")
        self.assertEqual(debates[0]["resolution"], "PENDING_CHIEF")
        self.assertEqual(debates[0]["response_required"], "TARGET_MUST_CONFIRM_OR_REVISE")


if __name__ == "__main__":
    unittest.main()
