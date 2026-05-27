from src.research.feedback_text_cleaner import FeedbackTextCleaner


def test_feedback_text_cleaner_extracts_g2_dislike_section():
    text = (
        "What do you like best about HubSpot Marketing Hub?"
        "The reporting is powerful and easy to use. "
        "Review collected by and hosted on G2.com."
        "What do you dislike about HubSpot Marketing Hub?"
        "The pricing is confusing and setup takes too long for small teams. "
        "Recommendations to others considering HubSpot Marketing Hub?"
        "Make sure you have someone technical."
    )

    result = FeedbackTextCleaner().extract_pain_text(text)

    assert "pricing is confusing" in result
    assert "setup takes too long" in result
    assert "The reporting is powerful" not in result
    assert "Recommendations to others" not in result


def test_feedback_text_cleaner_removes_g2_boilerplate():
    text = (
        "This tool is useful. "
        "Review collected by and hosted on G2.com. "
        "But onboarding is confusing."
    )

    result = FeedbackTextCleaner().clean(text)

    assert "Review collected by and hosted on G2.com" not in result
    assert "But onboarding is confusing." in result


def test_feedback_text_cleaner_falls_back_to_full_text_without_marker():
    text = "Customers complain that support replies are slow and setup is confusing."

    result = FeedbackTextCleaner().extract_pain_text(text)

    assert result == text


def test_feedback_text_cleaner_handles_empty_text():
    result = FeedbackTextCleaner().extract_pain_text("")

    assert result == ""
