import logging
import re
from typing import Any

from backend.app.core.config import settings

# Sensitive field patterns to redact in logs according to rule 80
REDACTION_PATTERNS = [
    re.compile(r'(?i)(["\']?(?:password|api_key|token|access_token|refresh_token|authorization|client_secret)["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])'),
    re.compile(r'(?i)(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*'),
    re.compile(r'(?i)\bsk-[a-zA-Z0-9_\-]{8,}\b'),
]


class SensitiveDataFilter(logging.Filter):
    """Filter that redacts sensitive credentials from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern in REDACTION_PATTERNS:
                if pattern.groups == 3:
                    msg = pattern.sub(r"\1***REDACTED***\3", msg)
                elif pattern.groups == 1:
                    msg = pattern.sub(r"\1***REDACTED***", msg)
                else:
                    msg = pattern.sub(r"***REDACTED***", msg)
            record.msg = msg

        if record.args:
            if isinstance(record.args, tuple):
                new_args = []
                for a in record.args:
                    if isinstance(a, str):
                        for pattern in REDACTION_PATTERNS:
                            if pattern.groups == 3:
                                a = pattern.sub(r"\1***REDACTED***\3", a)
                            elif pattern.groups == 1:
                                a = pattern.sub(r"\1***REDACTED***", a)
                            else:
                                a = pattern.sub(r"***REDACTED***", a)
                    new_args.append(a)
                record.args = tuple(new_args)
            elif isinstance(record.args, dict):
                new_dict = {}
                for k, v in record.args.items():
                    if isinstance(v, str):
                        for pattern in REDACTION_PATTERNS:
                            if pattern.groups == 3:
                                v = pattern.sub(r"\1***REDACTED***\3", v)
                            elif pattern.groups == 1:
                                v = pattern.sub(r"\1***REDACTED***", v)
                            else:
                                v = pattern.sub(r"***REDACTED***", v)
                    new_dict[k] = v
                record.args = new_dict
        return True


def setup_logging() -> None:
    """Configures structured application logging with sensitive data protection and UTF-8 console output."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    import sys
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(log_level)
    handler.addFilter(SensitiveDataFilter())

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Remove existing handlers to avoid duplicate output
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


logger = logging.getLogger("desktop_storage_manager")
