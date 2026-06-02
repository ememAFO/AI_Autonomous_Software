from src.utils.label_normalizer import LabelNormalizer


def test_label_normalizer_lowercases_labels():
    assert LabelNormalizer().normalize("Saas") == "saas"


def test_label_normalizer_converts_spaces_to_underscores():
    assert LabelNormalizer().normalize("United Airlines") == "united_airlines"


def test_label_normalizer_converts_mixed_symbols_to_single_underscore():
    assert LabelNormalizer().normalize("App-store Reviews") == "app_store_reviews"


def test_label_normalizer_keeps_existing_snake_case_clean():
    assert LabelNormalizer().normalize("g2_reviews") == "g2_reviews"


def test_label_normalizer_does_not_guess_semantic_meaning():
    assert LabelNormalizer().normalize("Baas") == "baas"


def test_label_normalizer_handles_empty_value():
    assert LabelNormalizer().normalize("") == "unknown"
