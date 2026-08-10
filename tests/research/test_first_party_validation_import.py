from __future__ import annotations

from pathlib import Path

import pytest

from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.research.first_party_validation_import import (
    FirstPartyImportError,
    FirstPartyImportService,
)
from tests.research.test_first_party_validation_review import (
    prepare_packet,
    write_decisions,
)


def prepare_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    review_service, packet = prepare_packet(tmp_path, monkeypatch)
    decisions = write_decisions(tmp_path, packet)
    return review_service.resolve(
        packet_file=Path(
            "reports/research/first_party_review_packets/packet.json"
        ),
        decision_file=decisions,
        output_file=Path(
            "reports/research/first_party_review_resolutions/"
            "resolution.json"
        ),
    )


def test_import_requires_explicit_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_resolution(tmp_path, monkeypatch)
    with pytest.raises(
        FirstPartyImportError,
        match="explicit",
    ):
        FirstPartyImportService().apply(
            resolution_file=Path(
                "reports/research/first_party_review_resolutions/"
                "resolution.json"
            ),
            output_file=Path(
                "reports/research/first_party_evidence_imports/"
                "import.json"
            ),
            import_reference="import-1",
            apply_changes=False,
        )


def test_import_adds_human_attested_primary_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_resolution(tmp_path, monkeypatch)
    result = FirstPartyImportService().apply(
        resolution_file=Path(
            "reports/research/first_party_review_resolutions/"
            "resolution.json"
        ),
        output_file=Path(
            "reports/research/first_party_evidence_imports/import.json"
        ),
        import_reference="import-1",
        apply_changes=True,
    )
    assert result.imported == 1
    entries = ValidationEvidenceLog().list_entries()
    assert entries[-1].source_trust == (
        ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY
    )
    assert entries[-1].evidence_type == "waitlist_signup"
    assert result.after_summary["gate_safe_primary_entries"] == 1
    assert all(
        value is False
        for value in result.protected_actions.values()
    )


def test_resolution_cannot_be_imported_twice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_resolution(tmp_path, monkeypatch)
    service = FirstPartyImportService()
    service.apply(
        resolution_file=Path(
            "reports/research/first_party_review_resolutions/"
            "resolution.json"
        ),
        output_file=Path(
            "reports/research/first_party_evidence_imports/import.json"
        ),
        import_reference="import-1",
        apply_changes=True,
    )
    Path(
        "reports/research/first_party_evidence_imports/import.json"
    ).unlink()
    with pytest.raises(
        FirstPartyImportError,
        match="already been imported",
    ):
        service.apply(
            resolution_file=Path(
                "reports/research/first_party_review_resolutions/"
                "resolution.json"
            ),
            output_file=Path(
                "reports/research/first_party_evidence_imports/"
                "import.json"
            ),
            import_reference="import-2",
            apply_changes=True,
        )


def test_verified_intake_tamper_blocks_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolution = prepare_resolution(tmp_path, monkeypatch)
    verified = Path(resolution.verified_intake_path)
    verified.write_text(
        verified.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        FirstPartyImportError,
        match="changed after",
    ):
        FirstPartyImportService().apply(
            resolution_file=Path(
                "reports/research/first_party_review_resolutions/"
                "resolution.json"
            ),
            output_file=Path(
                "reports/research/first_party_evidence_imports/"
                "import.json"
            ),
            import_reference="import-1",
            apply_changes=True,
        )
