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


def cmd_close_all_market(trader: Trader, data: dict) -> dict:
    """
    Manually close any positions related to this account/trader at market now.
    """
    results = {
        'messages': [],
        'error': False
    }

    positions = []

    with trader.mutex:
        for k, position in trader._positions.items():
            market = trader.market(position.symbol)

            if market:
                positions.append((position.position_id, market, position.direction, position.quantity))
            else:
                Terminal.inst().error("No market found to close position %s..." % position.position_id)

    for position in positions:
        # query close position
        try:
            trader.close_position(position[0], position[1], position[2], position[3], True, None)
            Terminal.inst().action("Closing position %s..." % position[0])
        except Exception as e:
            error_logger.error(repr(e))

    return results
