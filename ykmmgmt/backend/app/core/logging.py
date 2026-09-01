"""Logging setup — JSON lines in production, readable text in dev."""

import datetime
import json
import logging
import sys

LOG_FORMAT_JSON = "json"


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


def configure_logging(json_format: bool = False) -> None:
    """Install one stream handler on the root and uvicorn loggers.

    Called from scripts.serve (container/prod entrypoint) — the dev workflow
    (uvicorn --reload CLI) keeps uvicorn's own logging untouched.
    """
    formatter: logging.Formatter
    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("%(levelname)-5s [%(name)s] %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler]

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False
