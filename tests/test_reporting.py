from src.utils.reporting import ReportWriter


def test_report_generation(tmp_path):
    writer = ReportWriter(tmp_path)
    path = writer.write_report(
        category="testing",
        filename="testing_report.md",
        title="Testing Report",
        summary="Tests completed.",
    )
    assert path.exists()
    assert "# Testing Report" in path.read_text(encoding="utf-8")
