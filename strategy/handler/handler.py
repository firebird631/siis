# @date 2021-10-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy shared or local handler.

import threading

from datetime import datetime
from common.utils import timeframe_to_str, timeframe_from_str

import logging
logger = logging.getLogger('siis.strategy.handler')
error_logger = logging.getLogger('siis.error.strategy.handler')
traceback_logger = logging.getLogger('siis.traceback.strategy.handler')


class Handler(object):
    """
    Strategy trader shared or local handler base class.
    """

    NAME = "undefined"

    def __init__(self, context_id):
        self._context_id = context_id

        self._mutex = threading.RLock()

        self._installed_strategy_traders = []
        self._need_update = set()

    @classmethod
    def name(cls):
        """
        String type name of the handler.
        """
        return cls.NAME

    def install(self, strategy_trader):
        pass

    def process(self, strategy_trader):
        pass


class ReinvestGainHandler(Handler):
    """
    For each open, non partially realized trades, related to the context identifier
    or to a timeframe, cancel the trade and create a similar one with the new quantity.
    """

    NAME = "reinvest-gain"

    def __init__(self, context_id, trade_quantity, step_quantity):
        super().__init__(context_id)

        self._trade_quantity = trade_quantity
        self._step_quantity = step_quantity

        self._trade_quantity = 0.0
        self._total_max_trades = 0
        self._free_quantity = 0.0
        self._used_quantity = 0.0

    def install(self, strategy_trader):
        if strategy_trader and self._context_id:
            context = strategy_trader.retrieve_context(self._context_id)

            if context is None:
                # unable to retrieve related context
                return

            # @todo
            context.compute_quantity(strategy_trader)
            context.compute_quantity(strategy_trader)

    def uninstall(self, strategy_trader):
        if strategy_trader:
            with self._mutex:
                if strategy_trader in self._installed_strategy_traders:
                    self._installed_strategy_traders.remove(strategy_trader)

                if strategy_trader in self._need_update:
                    self._need_update.remove(strategy_trader)

    def process(self, strategy_trader):
        if not self._context_id:
            return

        context = strategy_trader.retrieve_context(self._context_id)

        if context is None:
            # unable to retrieve related context
            return

        need_update = False

        # retrieve last compute trade quantity
        trade_quantity = context.compute_quantity(strategy_trader.instrument)

        # with strategy_trader._trade_mutex:
        #     for trade in strategy_trader._trades:
        #         if trade.context and trade.context.name == self._context_id:
        #             if trade.order_quantity < trade_quantity:
        #                 self._resize_open_trade(strategy_trader, trade, trade_quantity)

        if need_update:
            with self._mutex:
                # require an update for each of the managed strategy-traders
                self._need_update = set(self._installed_strategy_traders)

        if strategy_trader in self._need_update:
            try:
                self._update_trades(strategy_trader)
            except Exception as e:
                error_logger.error(repr(e))

    def _update_trades(self, strategy_traders):
        pass

    def _resize_open_trade(self, strategy_trader, trade, trade_quantity):
        pass
