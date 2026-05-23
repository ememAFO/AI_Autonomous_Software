import json

import pytest

from src.utils.audit_logger import AuditEvent, AuditLogger, AuditLoggerError


def test_audit_logger_writes_jsonl_event():
    logger = AuditLogger(log_path="logs/test_audit.log")

    log_path = logger.log(
        AuditEvent(
            action="reddit_research_job",
            status="success",
            details={
                "query": "manual follow up",
                "subreddit": "smallbusiness",
                "processed_count": 2,
            },
        )
    )

    assert log_path.exists()

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    event = json.loads(lines[-1])

    assert event["action"] == "reddit_research_job"
    assert event["status"] == "success"
    assert event["details"]["query"] == "manual follow up"


def test_audit_logger_blocks_path_traversal():
    with pytest.raises(AuditLoggerError):
        AuditLogger(log_path="../../unsafe.log")


def test_audit_logger_blocks_non_log_extension():
    with pytest.raises(AuditLoggerError):
        AuditLogger(log_path="logs/audit.txt")


def test_audit_logger_redacts_secret_values():
    logger = AuditLogger(log_path="logs/test_audit.log")

    log_path = logger.log(
        AuditEvent(
            action="security_test",
            status="success",
            details={
                "api_key": "should-not-appear",
                "nested": {
                    "access_token": "also-secret",
                    "normal_value": "safe",
                },
            },
        )
    )

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    event = json.loads(lines[-1])

    assert event["details"]["api_key"] == "[REDACTED]"
    assert event["details"]["nested"]["access_token"] == "[REDACTED]"
    assert event["details"]["nested"]["normal_value"] == "safe"

    assert "should-not-appear" not in lines[-1]
    assert "also-secret" not in lines[-1]
