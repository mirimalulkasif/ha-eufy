"""Compatibility re-export — the integration speaks Mega bridge protocol."""

from .mega_client import EufyMegaClient as EufyWsClient
from .mega_client import EufyMegaError as EufyWsError

__all__ = ["EufyWsClient", "EufyWsError"]
