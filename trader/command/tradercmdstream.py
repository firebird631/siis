# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader command stream

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trader.trader import Trader


def cmd_trader_stream(trader: Trader, data: dict):
    """
    Subscribe/unsubscribe to different trader data stream :
        - trades or ticks data
        - OHLCs data
        - market Depth data
        - market update

    @param trader:
    @param data:
    @return:
    """
    results = {
        'messages': [],
        'error': False
    }

    # @todo

    return results
