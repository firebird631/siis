# @date 2024-07-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2024 Dream Overflow
# Strategy daily win/loss limits handler.

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Union, Dict

from common.utils import timestamp_to_str
from instrument.instrument import Instrument
from trader.trader import Trader

if TYPE_CHECKING:
    from strategy.strategytraderbase import StrategyTraderBase

from .handler import Handler

import logging
logger = logging.getLogger('siis.strategy.handler.dailylimithandler')
error_logger = logging.getLogger('siis.error.strategy.handler.dailylimithandler')
traceback_logger = logging.getLogger('siis.traceback.strategy.handler.dailylimithandler')


@dataclass
class DailyLimit:

    initial_balance: float = 0.0        # initial balance at installation of the handler or each new day (UTC)
    begin_timestamp: float = 0.0        # timestamp of the new day UTC 00h00m


class DailyLimitHandler(Handler):
    """
    This handler must be defined as global handler and not for a specific context.

    At each trade PNL update check if one of profit or loss limit is reached. If reached, set quantity to 0 until
    a new day begin.

    The limit can be configured in percent, weighed or not by quantity or in currency of the account.

    @note In backtesting the account currency could be incorrect because of the lack of base_exchange_rate.
    @note Because of its nature this handler is processed at each strategy trader update.
    @note It is not compatible with DCAHandler or ReinvestGainHandler.

    @todo Implement timezone offset
    @todo Implement cancel/close win/loss and add parameters to the command
    """

    NAME = "daily-limit"

    _trader = Trader

    _profit_limit_pct: float
    _profit_limit_currency: float
    _loss_limit_pct: float
    _loss_limit_currency: float

    _cancel_pending: bool
    _close_loosing: bool
    _close_winning: bool

    _timezone: float

    _daily_limit: DailyLimit

    _markets: Dict[StrategyTraderBase, float]

    def __init__(self, trader: Trader,
                 profit_limit_pct: float, profit_limit_currency: float,
                 loss_limit_pct: float, loss_limit_currency: float,
                 cancel_pending: bool = False,
                 close_loosing: bool = False,
                 close_winning: bool = False,
                 timezone: float = 0.0):
        """
        At least trader and one of profit limit in percentage or currency and one of loss limit in
        percentage or currency must be defined.

        @param trader: Valid trader.
        @param profit_limit_pct: Rate limit in profit, for a daily-win
        @param profit_limit_currency: Or in currency value of the account
        @param loss_limit_pct: Rate limit in loss, for a daily-loss
        @param loss_limit_currency: Or in currency value of the account
        @param cancel_pending: When lock trading also cancel opened (non-actives) trades
        @param close_loosing: When lock trading also close any loosing actives trades
        @param close_winning: When lock trading also close any winning actives trades
        @param timezone: A timezone value added to UTC timestamp (can be used as a session offset value)
        """
        super().__init__("")  # not related to a specific context

        self._trader = trader

        self._profit_limit_pct = profit_limit_pct
        self._profit_limit_currency = profit_limit_currency

        self._loss_limit_pct = loss_limit_pct
        self._loss_limit_currency = loss_limit_currency

        self._cancel_pending = cancel_pending
        self._close_loosing = close_loosing
        self._close_winning = close_winning

        self._timezone = timezone

        self._daily_limit = DailyLimit()

        self._markets = {}

        if self._trader:
            self._daily_limit.initial_balance = trader.account.balance
            self._daily_limit.begin_timestamp = Instrument.basetime(Instrument.TF_DAY, trader.timestamp)

    def install(self, strategy_trader: StrategyTraderBase):
        if strategy_trader:
            # already installed
            with self._mutex:
                if strategy_trader in self._installed_strategy_traders:
                    return

            with self._mutex:
                # update handler
                self._installed_strategy_traders.append(strategy_trader)

    def uninstall(self, strategy_trader: StrategyTraderBase):
        if strategy_trader:
            # not installed
            with self._mutex:
                if strategy_trader not in self._installed_strategy_traders:
                    return

            with self._mutex:
                # update handler
                if strategy_trader in self._installed_strategy_traders:
                    self._installed_strategy_traders.remove(strategy_trader)

                if strategy_trader in self._markets:
                    # restore previous quantity
                    with strategy_trader.mutex:
                        strategy_trader.instrument.trade_quantity = self._markets[strategy_trader]
                        del self._markets[strategy_trader]

    def process(self, strategy_trader: StrategyTraderBase):
        with self._mutex:
            if self._trader is None:
                return

            current_bt = Instrument.basetime(Instrument.TF_DAY, self._trader.timestamp)
            prev_bt = Instrument.basetime(Instrument.TF_DAY, self._daily_limit.begin_timestamp)

            elapsed_days = int((current_bt - prev_bt) / Instrument.TF_DAY)

            if elapsed_days > 0:
                self.new_session(current_bt)

            # empty _markets means not locked
            if not self._markets:
                check = self._check_limit()
                if check != 0:
                    self.lock_trading(check)

    def dumps(self, strategy_trader: StrategyTraderBase) -> Dict[str, Union[str, int, float]]:
        results = super().dumps(strategy_trader)

        results.update({
            'profit-limit-pct': self._profit_limit_pct,
            'profit-limit-currency': self._profit_limit_currency,
            'loss-limit-pct': self._loss_limit_pct,
            'loss-limit-currency': self._loss_limit_currency,
            'cancel-pending': self._cancel_pending,
            'close-loosing': self._close_loosing,
            'close-winning': self._close_winning,
        })

        return results

    def is_locked(self):
        with self._mutex:
            return len(self._markets) > 0

    def lock_trading(self, check: int):
        with self._mutex:
            logger.info("Trading is locked for any markets because of %s reached at %s" % (
                "daily-win" if check > 0 else "daily-loss", timestamp_to_str(self._trader.timestamp)))

            for strategy_trader in self._installed_strategy_traders:
                with strategy_trader.mutex:
                    # store actual quantity
                    self._markets[strategy_trader] = strategy_trader.instrument.trade_quantity

                    # set quantity to zero to avoid any new entry (forced 0 value)
                    strategy_trader.instrument._trade_quantity = 0

                    # cancel any pending trades
                    if self._cancel_pending:
                        pass

                    # close any winning trades
                    if self._close_winning:
                        pass

                    # close any loosing trades
                    if self._close_loosing:
                        pass

    def _check_limit(self):
        """This method is not thread-safe"""
        # check for a limit
        total_upnl = self._trader.account.profit_loss + self._trader.account.asset_profit_loss
        balance_diff = (self._trader.account.balance + total_upnl) - self._daily_limit.initial_balance

        if balance_diff < 0.0:
            # check for loss limit
            if self._loss_limit_pct > 0:
                if -balance_diff / self._daily_limit.initial_balance > self._loss_limit_pct:
                    return -1
            elif self._loss_limit_currency > 0:
                if -balance_diff > self._loss_limit_currency:
                    return -1

        elif balance_diff > 0.0:
            # check for profit limit
            if self._profit_limit_pct > 0:
                if balance_diff / self._daily_limit.initial_balance > self._profit_limit_pct:
                    return 1
            elif self._profit_limit_currency > 0:
                if balance_diff > self._profit_limit_currency:
                    return 1

        return 0

    def new_session(self, current_bt: float):
        with self._mutex:
            # reset for a new day
            self._daily_limit.initial_balance = self._trader.account.balance
            self._daily_limit.begin_timestamp = current_bt

            if self._markets and self._check_limit() == 0:
                logger.info("Trading is unlocked for any markets at %s" % timestamp_to_str(self._trader.timestamp))

                for strategy_trader in self._installed_strategy_traders:
                    if strategy_trader in self._markets:
                        # restore previous quantity
                        with strategy_trader.mutex:
                            strategy_trader.instrument.trade_quantity = self._markets[strategy_trader]
                            del self._markets[strategy_trader]
