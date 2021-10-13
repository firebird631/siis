# @date 2021-10-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy action.

from datetime import datetime
from common.utils import timeframe_to_str, timeframe_from_str


class Action(object):
    """
    Strategy trader action base class.
    """

    def __init__(self, context_id, timeframe):
        self._context_id = context_id
        self._timeframe = timeframe

    def process(self, strategy_trade):
        pass


class ResizeOpenTrade(Action):
    """
    For each open, non partially realized trades, related to the context identifier
    or to a timeframe, cancel the trade and create a similar one with the new quantity.
    """
    def __init__(self, context_id, timeframe):
        super().__init__(context_id, timeframe)

    def process(self, strategy_trader):
        if self._context_id:
            context = strategy_trader.retrieve_context(self._context_id)

            if context is None:
                # unable to retrieve related context
                return

            # retrieve last compute trade quantity
            trade_quantity = context.compute_quantity(strategy_trader.instrument)

            with strategy_trader._trade_mutex:
                for trade in strategy_trader._trades:
                    if trade.context and trade.context.name == self._context_id:
                        if trade.order_quantity < trade_quantity:
                            self.resize_open_trade(strategy_trader, trade, trade_quantity)

        elif self._timeframe:
            trade_quantity = strategy_trader.instrument.trade_quantity

            with strategy_trader._trade_mutex:
                for trade in strategy_trader._trades:
                    pass

    def resize_open_trade(self, strategy_trader, trade, trade_quantity):
        pass
