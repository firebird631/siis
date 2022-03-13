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


def cmd_close_market(trader: Trader, data: dict) -> dict:
    """
    Manually close a specified position at market now.
    """
    results = {
        'messages': [],
        'error': False
    }

    position_id = None
    direction = 0
    quantity = 0.0
    market = None

    with trader.mutex:
        for k, position in trader._positions.items():
            if position.key == data['key']:
                position_id = position.position_id
                direction = position.direction
                quantity = position.quantity

                market = trader.market(position.symbol)

    if position_id:
        # query close position
        if market:
            try:
                trader.close_position(position_id, market, direction, quantity, True, None)
                Terminal.inst().action("Closing position %s..." % (position_id,))
            except Exception as e:
                error_logger.error(repr(e))
        else:
            Terminal.inst().error("No market found to close position %s" % (position_id,))
    else:
        Terminal.inst().error("No position found to close for key %s" % (data['key'],))

    return results
