# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader info command

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trader.trader import Trader

from terminal.terminal import Terminal

from trader.order import Order

import logging

logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')
traceback_logger = logging.getLogger('siis.traceback.trader')


def cmd_sell_all_asset(trader: Trader, data: dict) -> dict:
    results = {
        'messages': [],
        'error': False
    }

    assets = []

    with trader.mutex:
        try:
            for k, asset in trader._assets.items():
                # query create order to sell any asset quantity
                # try over the primary currency, then over the alt one
                # user could have to to it in two phase
                market = None

                if k == trader.account.currency:
                    # don't sell account currency
                    continue

                for market_id in asset.market_ids:
                    m = trader.market(market_id)

                    if m.quote == trader.account.currency:
                        market = m  # first choice
                        break

                    # elif m.quote == trader.account.alt_currency:
                    #     market = m  # second choice

                if asset.free <= 0.0:
                    continue

                if market:
                    assets.append((asset.symbol, market, asset.free))
                else:
                    Terminal.inst().error("No market found to sell all for asset %s..." % (asset.symbol,))

            for asset in assets:
                market = asset[1]

                order = Order(trader, market.market_id)
                order.direction = Order.SHORT
                order.order_type = Order.ORDER_MARKET
                order.quantity = asset[2]

                # generated a reference order id
                trader.set_ref_order_id(order)

                if trader.create_order(order, market) > 0:
                    Terminal.inst().action("Create order %s to sell all of %s on %s..." % (
                        order.order_id, asset[0], market.market_id))
                else:
                    Terminal.inst().action("Rejected order to sell all of %s on %s..." % (
                        asset[0], market.market_id))
        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

    return results
