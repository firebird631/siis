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

    def on_trade_opened(self, strategy_trader, trade):
        """
        Called when a trade is added.
        """
        pass

    def on_trade_exited(self, strategy_trader, trade):
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

    @note Only process spot/asset trades.
    @todo Support for margin and position trades
    """

    NAME = "reinvest-gain"

    def __init__(self, context_id, trade_quantity, step_quantity):
        super().__init__(context_id)

        self._trade_quantity = trade_quantity
        self._step_quantity = step_quantity

        self._total_max_trades = 0
        self._used_quantity = 0.0
        self._total_quantity = 0.0
        self._num_trades = 0

    def install(self, strategy_trader):
        if strategy_trader in self._installed_strategy_traders:
            return

        if strategy_trader and self._context_id:
            context = strategy_trader.retrieve_context(self._context_id)

            if context is None:
                # unable to retrieve related context
                return

            context.modify_trade_quantity_type(strategy_trader.instrument, 'managed', self._step_quantity)

            # initial trade quantity
            context.trade_quantity = self._trade_quantity

            used_quantity = 0
            num_trades = 0

            with strategy_trader._trade_mutex:
                for trade in strategy_trader._trades:
                    if trade.context == context:
                        # compute quantity from trade
                        trade_price = trade.order_price if trade.order_price > 0 else trade.entry_price
                        trade_quantity = trade.order_quantity

                        used_quantity += trade_quantity * trade_price
                        num_trades += 1

            with self._mutex:
                # update handler
                self._installed_strategy_traders.append(strategy_trader)

                self._total_max_trades += context.max_trades
                self._total_quantity += strategy_trader.instrument.adjust_quote(
                    context.max_trades * context.trade_quantity)

                self._used_quantity += strategy_trader.instrument.adjust_quote(used_quantity)
                self._num_trades += num_trades

    def uninstall(self, strategy_trader):
        if strategy_trader not in self._installed_strategy_traders:
            return

        if strategy_trader and self._context_id:
            context = strategy_trader.retrieve_context(self._context_id)

            if context is None:
                # unable to retrieve related context
                return

            released_quantity = 0

            with strategy_trader._trade_mutex:
                for trade in strategy_trader._trades:
                    if trade.context == context:
                        # compute quantity from trade
                        trade_price = trade.order_price if trade.order_price > 0 else trade.entry_price
                        trade_quantity = trade.order_quantity

                        released_quantity += trade_quantity * trade_price

            with self._mutex:
                # update handler
                if strategy_trader in self._installed_strategy_traders:
                    self._installed_strategy_traders.remove(strategy_trader)

                if strategy_trader in self._need_update:
                    self._need_update.remove(strategy_trader)

                self._total_max_trades -= context.max_trades
                if self._total_max_trades < 0:
                    self._total_max_trades = 0

                self._total_quantity -= context.max_trades * context.trade_quantity
                if self._total_quantity < 0.0:
                    self._total_quantity = 0.0

                self._used_quantity -= released_quantity
                if self._used_quantity < 0.0:
                    self._used_quantity = 0.0

            context.modify_trade_quantity_type(strategy_trader.instrument, 'normal')

    def on_setting_changed(self, strategy_trader):
        # @todo
        pass

    def on_trade_opened(self, strategy_trader, trade):
        if trade and trade.context and trade.context.name == self._context_id:
            trade_price = trade.order_price if trade.order_price > 0 else trade.entry_price
            trade_quantity = trade.order_quantity

            entry_quantity = trade_quantity * trade_price

            with self._mutex:
                self._used_quantity += strategy_trader.instrument.adjust_quote(entry_quantity)
                self._num_trades += 1

    def on_trade_exited(self, strategy_trader, trade):
        if trade and trade.context and trade.context.name == self._context_id:
            entry_quantity = trade.exec_entry_qty * trade.entry_price
            exit_quantity = trade.exec_exit_qty * trade.exit_price

            trade_price = trade.order_price if trade.order_price > 0 else trade.entry_price
            trade_quantity = trade.order_quantity

            profit_loss = exit_quantity - entry_quantity

            with self._mutex:
                self._total_quantity += profit_loss

                self._used_quantity -= strategy_trader.instrument.adjust_quote(trade_quantity * trade_price)
                if self._used_quantity < 0.0:
                    self._used_quantity = 0.0

                self._num_trades -= 1
                if self._num_trades < 0.0:
                    self._num_trades = 0.0

                max_quantity = int(self._total_max_trades / self._total_max_trades)
                inc_step = int((max_quantity - self._trade_quantity) / self._step_quantity)

                if inc_step > 0:
                    self._trade_quantity += inc_step

                    # update any strategy trader
                    self._need_update = set(self._installed_strategy_traders)

    def process(self, strategy_trader):
        if not self._context_id:
            return

        if strategy_trader not in self._need_update:
            return

        with self._mutex:
            self._need_update.remove(strategy_trader)

        context = strategy_trader.retrieve_context(self._context_id)
        if context is None:
            return

        # update trade quantity for strategy trader context
        context.trade_quantity = self._trade_quantity

        if self._trade_quantity > 0:
            # reopen pending orders
            self._resize_open_trades(strategy_trader, context, context.trade_quantity)

    def _resize_open_trades(self, strategy_trader, context, new_trade_quantity):
        with strategy_trader._trade_mutex:
            trader = strategy_trader.strategy.trader()

            for trade in strategy_trader._trades:
                if trade.context == context and trade.is_opened() and trade.order_price > 0:
                    cur_trade_quantity = trade.order_quantity * trade.order_price

                    if abs(new_trade_quantity - cur_trade_quantity) >= self._step_quantity:
                        # the asset quantity for quote could not be up to date at this time
                        # quantity = strategy_trader.compute_asset_quantity(
                        #     trader, trade.order_price, new_trade_quantity)

                        quantity = strategy_trader.instrument.adjust_quantity(new_trade_quantity / trade.order_price)

                        try:
                            if not trade.cancel_open(strategy_trader, strategy_trader.instrument):
                                logger.error("Unable to cancel trade %s open for %s" % (
                                    trade.id, strategy_trader.instrument.symbol))
                                continue

                            if not trade.reopen(trader, strategy_trader.instrument, quantity):
                                # will be removed automatically
                                logger.error("Unable to reopen trade %s open for %s" % (
                                    trade.id, strategy_trader.instrument.symbol))
                                continue

                        except Exception as e:
                            error_logger.error(repr(e))

    def dumps(self):
        results = super().dumps()

        results.update({
            'trade-quantity': self._trade_quantity,
            'step-quantity': self._step_quantity,
            'num-trades': self._num_trades,
            'total-max-trades': self._total_max_trades,
            'used-quantity': self._used_quantity,
            'total-quantity': self._total_quantity
        })

        return results
