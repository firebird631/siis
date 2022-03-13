# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader info command

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trader.trader import Trader

import logging

logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')


def cmd_trader_info(trader: Trader, data: dict) -> dict:
    """
    Info on the global trader instance.
    """
    results = {
        'messages': [],
        'error': False
    }

    # @todo

    return results
