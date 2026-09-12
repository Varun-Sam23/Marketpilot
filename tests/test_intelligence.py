from news_intelligence import claim_status, evidence_score, similarity


def test_claim_status_is_conservative():
    status, _ = claim_status("UNVERIFIED", [], [])
    assert status == "INSUFFICIENT EVIDENCE"

    status, _ = claim_status("SINGLE_SOURCE", ["Publisher A"], ["POSITIVE"])
    assert status == "INSUFFICIENT EVIDENCE"

    status, _ = claim_status("CROSS_CHECKED", ["Publisher A", "Publisher B"], ["POSITIVE", "POSITIVE"])
    assert status == "SUPPORTED"

    status, _ = claim_status("CONFLICTING", ["Publisher A", "Publisher B"], ["POSITIVE", "NEGATIVE"])
    assert status == "DISPUTED"


def test_evidence_score_bounds():
    assert evidence_score("UNVERIFIED", 0) == 10
    assert evidence_score("SINGLE_SOURCE", 1) == 30
    assert 0 <= evidence_score("CORROBORATED", 4) <= 100
    assert 0 <= evidence_score("CROSS_CHECKED", 10) <= 100
    assert evidence_score("CONFLICTING", 4) == 35


def test_headline_similarity_is_reasonable():
    assert similarity("Nifty rises after RBI decision", "Nifty rises after RBI decision") == 1.0
    assert similarity("Nifty rises after RBI decision", "Nifty falls after RBI decision") > 0.2
    assert similarity("Indian bank earnings strong", "European football results") < 0.2
