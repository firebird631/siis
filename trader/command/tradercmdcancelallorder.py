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


def cmd_cancel_all_order(trader: Trader, data: dict) -> dict:
    results = {
        'messages': [],
        'error': False
    }

    orders = []

    # None or a specific market only
    market_id = data.get('market-id')
    options = data.get('options')

    with trader.mutex:
        for k, order in trader._orders.items():
            market = trader.market(order.symbol)

            if market is None:
                Terminal.inst().error("No market found to cancel order %s..." % (order.order_id,))
                continue

            if market_id and market_id != market.market_id:
                # ignored market-id
                continue

            if options:
                # ("spot-entry", "spot-exit", "margin-entry", "margin-exit")
                accept = False

                if "spot-entry" in options:
                    if market.has_spot and order.direction > 0:
                        accept = True

                if "spot-exit" in options:
                    if market.has_spot and order.direction < 0:
                        accept = True

                if "margin-entry" in options:
                    if market.has_margin and not order.reduce_only and not order.close_only:
                        accept = True

                if "margin-exit" in options:
                    if market.has_margin and order.reduce_only or order.close_only:
                        accept = True

                if not accept:
                    continue

            orders.append((order.order_id, market))

    for order in orders:
        # query cancel order
        try:
            if trader.cancel_order(order[0], order[1]) > 0:
                Terminal.inst().action("Cancel order %s..." % order[0])
        except Exception as e:
            error_logger.error(repr(e))

    return results
