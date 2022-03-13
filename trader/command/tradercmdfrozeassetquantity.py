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


def cmd_trader_froze_asset_quantity(trader: Trader, data: dict) -> dict:
    """
    Lock a quantity of an asset to be not available for trading.
    """
    results = {
        'messages': [],
        'error': False
    }

    asset_name = data.get('asset')
    quantity = data.get('quantity', -1.0)

    if not asset_name:
        Terminal.inst().error("Asset to froze quantity must be specified")

    if quantity < 0.0:
        Terminal.inst().error("Asset quantity to froze must be specified and greater or equal to zero")

    # @todo

    return results
