"""Offline runtime policy: no telemetry, no model-hub access, loopback-only networking."""

import ipaddress
import os
from urllib.parse import urlparse

OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "ANONYMIZED_TELEMETRY": "False",
}


def apply_offline_env() -> None:
    """Force offline/telemetry-off flags. Overrides any value already set in the environment."""
    os.environ.update(OFFLINE_ENV)


def is_loopback_host(host: str) -> bool:
    host = host.strip().strip("[]")
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def url_host(url: str) -> str:
    return urlparse(url).hostname or ""
