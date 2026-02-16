"""Logging configuration for the application."""

import logging


def configure_logging(level: int) -> None:
    logging.basicConfig(
        level=level,
        format="[%(asctime)s | %(levelname)s] %(message)s",
        force=True,
    )
