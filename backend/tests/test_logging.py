import logging
from backend.app.core.logging import SensitiveDataFilter, setup_logging


def test_sensitive_data_redaction():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Connecting with api_key='sk-1234567890abcdef' and password=\"supersecret\"",
        args=(),
        exc_info=None,
    )
    filter_ = SensitiveDataFilter()
    filter_.filter(record)
    assert "sk-1234567890abcdef" not in record.msg
    assert "supersecret" not in record.msg
    assert "***REDACTED***" in record.msg
