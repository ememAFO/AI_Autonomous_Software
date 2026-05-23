from src.analyzers.pain_extractor import PainExtractor


def test_pain_extractor_detects_business_pain():
    text = "I keep losing leads because I forget to follow up with clients after sending quotes."

    result = PainExtractor().extract(text)

    assert result.is_business_pain is True
    assert result.frustration_score > 0
    assert "losing leads" in result.matched_terms
    assert "follow up" in result.matched_terms
    assert "clients" in result.matched_terms


def test_pain_extractor_rejects_empty_text():
    result = PainExtractor().extract("")

    assert result.is_business_pain is False
    assert result.frustration_score == 0
    assert result.matched_terms == []


def test_pain_extractor_does_not_mark_general_complaint_as_business_pain():
    text = "This app is annoying but I only use it for personal notes."

    result = PainExtractor().extract(text)

    assert result.is_business_pain is False
    assert "annoying" in result.matched_terms


def test_pain_extractor_can_process_many_texts():
    texts = [
        "Clients stop replying after quotes and I waste time chasing them.",
        "I like the colour of this app.",
        "Manual appointment booking takes too long for our staff.",
    ]

    results = PainExtractor().extract_many(texts)

    assert len(results) == 3
    assert results[0].is_business_pain is True
    assert results[1].is_business_pain is False
    assert results[2].is_business_pain is True
