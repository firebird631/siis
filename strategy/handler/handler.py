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

    #
    # slots
    #

    def on_setting_changed(self, strategy_trader):
        """
        Called when a changes occurs on a setting.
        """
        pass

    def on_new_trade(self, trade):
        """
        Called when a trade is added.
        """
        pass

    def on_close_trade(self, trade):
        """
        Called when a trade is remove (closed or canceled).
        """
        pass

    #
    # setup
    #

    def install(self, strategy_trader):
        pass

    def uninstall(self, strategy_trader):
        pass

    #
    # process
    #

    def process(self, strategy_trader):
        pass

    #
    # report
    #

    def dumps(self):
        return {
            'name': self.name(),
            'context': self._context_id
        }


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

        self._total_max_trades = 0
        self._used_quantity = 0.0
        self._total_quantity = 0.0

    def install(self, strategy_trader):
        if strategy_trader and self._context_id:
            context = strategy_trader.retrieve_context(self._context_id)

            if context is None:
                # unable to retrieve related context
                return

            context.modify_trade_quantity_type(strategy_trader.instrument, 'global-share', self._step_quantity)

            # initial trade quantity
            context.trade_quantity = self._trade_quantity

            # update handler
            self._total_max_trades += context.max_trades
            self._total_quantity += context.max_trades * context.trade_quantity

            with strategy_trader._trade_mutex:
                for trade in strategy_trader._trades:
                    if trade.context == context:
                        # compute quantity from trade
                        trade_price = trade.entry_price if trade.entry_price else trade.order_price

                        self._used_quantity += trade.order_quantity * trade_price

    def uninstall(self, strategy_trader):
        if strategy_trader and self._context_id:
            context = strategy_trader.retrieve_context(self._context_id)

            if context is None:
                # unable to retrieve related context
                return

            with self._mutex:
                if strategy_trader in self._installed_strategy_traders:
                    self._installed_strategy_traders.remove(strategy_trader)

                if strategy_trader in self._need_update:
                    self._need_update.remove(strategy_trader)

                # update handler
                self._total_max_trades -= context.max_trades
                if self._total_max_trades < 0:
                    self._total_max_trades = 0

                self._total_quantity -= context.max_trades * context.trade_quantity
                if self._total_quantity < 0.0:
                    self._total_quantity = 0.0

                with strategy_trader._trade_mutex:
                    for trade in strategy_trader._trades:
                        if trade.context == context:
                            # compute quantity from trade
                            trade_price = trade.entry_price if trade.entry_price else trade.order_price

                            self._used_quantity -= trade.order_quantity * trade_price
                            if self._used_quantity < 0.0:
                                self._used_quantity = 0.0

                context.modify_trade_quantity_type(strategy_trader.instrument, 'normal')

    def on_setting_changed(self, strategy_trader):
        pass

    def on_new_trade(self, trade):
        pass

    def on_close_trade(self, trade):
        if trade:
            entry_quantity = trade.exec_entry_qty * trade.entry_price
            exit_quantity = trade.exec_exit_qty * trade.exit_price

            profit_loss = exit_quantity - entry_quantity

            self._total_quantity += profit_loss
            self._used_quantity -= entry_quantity

    def process(self, strategy_trader):
        if not self._context_id:
            return

        context = strategy_trader.retrieve_context(self._context_id)

        if context is None:
            # unable to retrieve related context
            return

        need_update = False
        new_trade_quantity = 0.0

        # retrieve last compute trade quantity
        prev_trade_quantity = context.compute_quantity(strategy_trader.instrument)

        # if need_update:
        #     with self._mutex:
        #         # require an update for each of the managed strategy-traders
        #         self._need_update = set(self._installed_strategy_traders)

        if 0.0 > new_trade_quantity > context.trade_quantity:
            # update context trade quantity
            context.trade_quantity = new_trade_quantity

            # reopen pending orders
            self._resize_open_trades(strategy_trader, context, new_trade_quantity)

    def _resize_open_trades(self, strategy_trader, context, new_trade_quantity):
        with strategy_trader._trade_mutex:
            for trade in strategy_trader._trades:
                if trade.context == context and trade.is_opened():
                    if trade.order_quantity != new_trade_quantity:
                        try:
                            pass  # @todo
                        except Exception as e:
                            error_logger.error(repr(e))

    def dumps(self):
        results = super().dumps()

        results.update({
            'trade-quantity': self._trade_quantity,
            'step-quantity': self._step_quantity,
            'total-max-trades': self._total_max_trades,
            'used-quantity': self._used_quantity,
            'total-quantity': self._total_quantity
        })

        return results
