"""Logging configuration for the application."""

import logging
from typing import Optional

from pydantic import BaseModel
from rich.logging import RichHandler


def configure_logging(level: int) -> None:
    logging.basicConfig(
        level=level,
        format="%(name)s: %(message)s",
        datefmt="[%H:%M:%S]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
        force=True,
    )


def debug_dump_model_json(
    logger: logging.Logger,
    label: str,
    model: Optional[BaseModel],
    *,
    indent: int = 2,
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    if model is None:
        logger.debug("[%s] <None>", label)
        return
    try:
        logger.debug("[%s]\n%s", label, model.model_dump_json(indent=indent))
    except Exception:
        logger.exception("Failed to dump model JSON for %s", label)
