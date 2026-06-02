import re


class LabelNormalizer:
    """
    Normalizes user-provided labels for clean reporting.

    Purpose:
    - keep industry/source labels consistent
    - avoid report pollution from casing differences
    - avoid guessing semantic meaning
    """

    MAX_LABEL_LENGTH = 80

    def normalize(self, value: str) -> str:
        text = str(value or "").strip().lower()

        text = re.sub(r"[^a-z0-9]+", "_", text)
        text = re.sub(r"_+", "_", text)
        text = text.strip("_")

        return text[: self.MAX_LABEL_LENGTH] or "unknown"
