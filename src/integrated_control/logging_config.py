"""Application-wide configuration for Python's standard logging system."""

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure the standard logging format and requested severity level."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
