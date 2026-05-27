import re


class FeedbackTextCleaner:
    """
    Extracts the most useful pain/problem section from long feedback text.

    Purpose:
    - isolate complaint/dislike sections from mixed reviews
    - remove review platform boilerplate
    - keep positive review sections from diluting business pain detection
    """

    BOILERPLATE_PATTERNS = [
        "Review collected by and hosted on G2.com.",
        "Review collected by and hosted on G2.com",
    ]

    DISLIKE_MARKERS = [
        "What do you dislike about",
        "What do you dislike",
        "What problems is",
        "What problems are",
        "What needs improvement",
        "Cons:",
        "Dislikes:",
        "Negative:",
    ]

    END_MARKERS = [
        "What do you like best",
        "What do you like",
        "Recommendations to others",
        "What problems is the product solving",
        "What problems are you solving",
        "Describe the benefits",
        "Review collected by and hosted on G2.com",
    ]

    def extract_pain_text(self, text: str) -> str:
        cleaned = self.clean(text)

        extracted = self._extract_after_marker(cleaned)

        return extracted or cleaned

    def clean(self, text: str) -> str:
        value = str(text or "")

        for pattern in self.BOILERPLATE_PATTERNS:
            value = value.replace(pattern, " ")

        value = re.sub(r"\s+", " ", value)

        return value.strip()

    def _extract_after_marker(self, text: str) -> str:
        lowered = text.lower()

        marker_positions = []

        for marker in self.DISLIKE_MARKERS:
            position = lowered.find(marker.lower())

            if position != -1:
                marker_positions.append((position, marker))

        if not marker_positions:
            return ""

        start_position, marker = min(marker_positions, key=lambda item: item[0])
        content_start = start_position + len(marker)

        next_end_positions = []

        for end_marker in self.END_MARKERS:
            position = lowered.find(end_marker.lower(), content_start)

            if position != -1:
                next_end_positions.append(position)

        content_end = min(next_end_positions) if next_end_positions else len(text)

        extracted = text[content_start:content_end]

        extracted = extracted.lstrip("?:.- |")
        extracted = re.sub(r"\s+", " ", extracted)

        return extracted.strip()
