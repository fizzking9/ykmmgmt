"""Container API entrypoint — uvicorn with our logging configuration.

LOG_FORMAT=json (set by the production compose file) emits single-line JSON
records for all loggers; anything else keeps the readable dev format.
"""

import os

import uvicorn

from app.core.logging import LOG_FORMAT_JSON, configure_logging


def main() -> None:
    configure_logging(json_format=os.getenv("LOG_FORMAT", "text") == LOG_FORMAT_JSON)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_config=None,  # our configure_logging owns the handlers
    )


if __name__ == "__main__":
    main()
