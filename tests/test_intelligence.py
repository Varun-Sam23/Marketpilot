import unittest

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


if __name__ == "__main__":
    unittest.main()
