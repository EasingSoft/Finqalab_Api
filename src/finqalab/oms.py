"""OMS trade-intimation logging (``finqalab-oms-prod.finqalab.com``).

The app fires this after a STOMP order action so the OMS records the
intimation even if the notification isn't delivered. Purely informational.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

from .config import OMS_BASE, OMS

logger = logging.getLogger("finqalab.oms")


def trade_intimation(payload: Dict[str, Any]) -> Any:
    """POST the trade-intimation payload to the OMS logger.

    ``payload`` should contain whatever the app logs (order no, side,
    symbol, etc.); the exact schema is inferred from capture since the
    endpoint returned no meaningful body.
    """
    resp = requests.post(
        OMS_BASE + OMS["trade_intimation"],
        json=payload,
        headers={"content-type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        return resp.text
