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


def cmd_trader_ticker_memset(trader: Trader, data: dict) -> dict:
    """
    Memorize the last market price for any or a specific market.
    """
    results = {
        'messages': [],
        'error': False
    }

    market_id = data.get('market-id')

    if market_id:
        market = trader.find_market(market_id)

        if market is None:
            results['messages'].append("Market %s not found !" % market_id)
            results['error'] = True
            return results

        with trader.mutex:
            market.mem_set()
    else:
        with trader.mutex:
            for market_id, market in trader._markets.items():
                market.mem_set()

    return results
