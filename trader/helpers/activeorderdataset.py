# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader dataset to display table for views and formatters

import logging
import traceback

logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')
traceback_logger = logging.getLogger('siis.traceback.trader')


def get_active_orders(trader):
    """
    Generate and return an array of all active orders :
        symbol: str market identifier
        id: int order identifier
        refid: int ref order identifier
    """
    results = []

    with trader.mutex:
        try:
            for k, order in trader._orders.items():
                market = trader._markets.get(order.symbol)
                if market:
                    results.append({
                        'mid': market.market_id,
                        'sym': market.symbol,
                        'id': order.order_id,
                        'refid': order.ref_order_id,
                        'ct': order.created_time,
                        'tt': order.transact_time,
                        'd': order.direction_to_str(),
                        'ot': order.order_type_to_str(),
                        'l': order.leverage,
                        'q': market.format_quantity(order.quantity),
                        'op': market.format_price(order.price) if order.price else "",
                        'sp': market.format_price(order.stop_price) if order.stop_price else "",
                        'sl': market.format_price(order.stop_loss) if order.stop_loss else "",
                        'tp': market.format_price(order.take_profit) if order.take_profit else "",
                        'tr': "No",
                        'xq': market.format_quantity(order.executed),
                        'ro': order.reduce_only,
                        'he': order.hedging,
                        'po': order.post_only,
                        'co': order.close_only,
                        'mt': order.margin_trade,
                        'tif': order.time_in_force_to_str(),
                        'pt': order.price_type_to_str(),
                        'key': order.key
                    })
        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

    return results
