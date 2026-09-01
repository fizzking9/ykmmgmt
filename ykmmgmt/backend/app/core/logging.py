"""Logging setup — JSON lines in production, readable text in dev.

Optionally mirrors every record into a rotating file (LOG_FILE) so logs
are inspectable as plain files on the host, not only via `docker logs`.
"""

import datetime
import json
import logging
import logging.handlers
import sys

LOG_FORMAT_JSON = "json"
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file, 5 backups
LOG_FILE_BACKUP_COUNT = 5


class JsonFormatter(logging.Formatter):
    """Single-line JSON per record; Chinese messages stay readable (no \\u escapes)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(json_format: bool = False, log_file: str | None = None) -> None:
    """Install handlers on the root and uvicorn loggers.

    Called from scripts.serve (container/prod entrypoint) — the dev workflow
    (uvicorn --reload CLI) keeps uvicorn's own logging untouched.

    When log_file is set (LOG_FILE env in the prod compose file), every record
    is mirrored into that rotating file on the host-mounted logs volume.
    """
    formatter: logging.Formatter
    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("%(levelname)-5s [%(name)s] %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handlers: list[logging.Handler] = [handler]

    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = handlers

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = handlers
        logger.propagate = False
