# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader info command

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trader.trader import Trader

from terminal.terminal import Terminal

import logging

logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')


def cmd_cancel_order(trader: Trader, data: dict) -> dict:
    results = {
        'messages': [],
        'error': False
    }

    market_id = data.get('market-id')
    order_id = data.get('order-id')

    market = trader.market(market_id)

    if market is None:
        Terminal.inst().error("No market found to cancel order %s..." % (order_id,))

    # query cancel order
    try:
        if trader.cancel_order(order_id, market) > 0:
            Terminal.inst().action("Cancel order %s..." % order_id)
    except Exception as e:
        results['error'] = True
        results['messages'].append(repr(e))

        error_logger.error(repr(e))

    return results
