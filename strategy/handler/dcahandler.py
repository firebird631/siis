# @date 2021-10-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy dollar cost average handler.

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple, Union, Dict, List

if TYPE_CHECKING:
    from strategy.strategytrader import StrategyTrader
    from strategy.trade.strategytrade import StrategyTrade

from strategy.trade.strategyassettrade import StrategyAssetTrade

from dataclasses import dataclass, field

from .handler import Handler

import logging
logger = logging.getLogger('siis.strategy.handler.dcahandler')
error_logger = logging.getLogger('siis.error.strategy.handler.dcahandler')
traceback_logger = logging.getLogger('siis.traceback.strategy.handler.dcahandler')


@dataclass
class DCAMarketData:

    total_quantity: float = 0.0
    entry_trades_ids: list = field(default_factory=list)
    exit_trades_ids: list = field(default_factory=list)
    exit_prices: list = field(default_factory=list)


class DCAHandler(Handler):
    """
    This handler is only dedicated to spot/asset market.
    This handler must be defined as global handler and not for a specific context.

    Each time there is more than one active trade on an market this handler
    do a fusion, recomputing the average entry price and the quantity.
    Many take profit will be then managed, from one to many.

    The percent of quantity sold can be divided into equals parts of many defined possibles
    take profit or the percent can be defined. If the sum of percent does not equal 100
    then the rest is let to an additional take profit without initial target price.

    The handler will never allow to sell at a negative PNL of the average entry price.

    @note Only process spot/asset trades.
    """

    NAME = "dca"

    _num_take_profits: int
    _percentiles: Optional[Tuple[int]]
    _markets: Dict[StrategyTrader, DCAMarketData]

    def __init__(self, context_id: str, num_take_profits: int, percentiles: Optional[Tuple[int]]):
        super().__init__(context_id)

        self._num_take_profits = num_take_profits
        self._percentiles = percentiles

        self._markets = {}  # per market local data

    @property
    def num_take_profits(self) -> int:
        return self._num_take_profits

    @property
    def percentiles(self) -> Union[Tuple[int], None]:
        return self._percentiles

    def install(self, strategy_trader: StrategyTrader):
        if strategy_trader:
            # already installed
            with self._mutex:
                if strategy_trader in self._installed_strategy_traders:
                    return

            with strategy_trader.trade_mutex:
                market_data = DCAMarketData()

                for trade in strategy_trader.trades:
                    # retrieve entry trades, no exits trades or they are unrelated
                    if trade.is_active() and trade.entry_state == StrategyTrade.STATE_FILLED:
                        market_data.entry_trades_ids.append(trade.id)
                        pending_quantity = strategy_trader.instrument.adjust_quantity(
                            trade.exec_entry_qty - trade.exec_exit_qty)
                        market_data.total_quantity += pending_quantity

            with self._mutex:
                # update handler
                self._markets[strategy_trader] = market_data
                self._installed_strategy_traders.append(strategy_trader)

                # first time need update
                if strategy_trader not in self._need_update:
                    self._need_update.add(strategy_trader)

    def uninstall(self, strategy_trader: StrategyTrader):
        if strategy_trader and self._context_id:
            # not installed
            with self._mutex:
                if strategy_trader not in self._installed_strategy_traders:
                    return

            with self._mutex:
                # update handler
                if strategy_trader in self._installed_strategy_traders:
                    self._installed_strategy_traders.remove(strategy_trader)

                if strategy_trader in self._need_update:
                    self._need_update.remove(strategy_trader)

                if strategy_trader in self._markets:
                    del self._markets[strategy_trader]

    def on_trade_opened(self, strategy_trader: StrategyTrader, trade: StrategyTrade):
        if trade is not None:
            pass

    def on_trade_updated(self, strategy_trader: StrategyTrader, trade: StrategyTrade):
        if trade is not None:
            # realized quantity could have increased
            with self._mutex:
                if strategy_trader not in self._need_update:
                    self._need_update.add(strategy_trader)

    def on_trade_exited(self, strategy_trader: StrategyTrader, trade: StrategyTrade):
        if trade is not None:
            # remove an exit trade it
            with self._mutex:
                # update handler
                market_data = self._markets.get(strategy_trader)
                if market_data:
                    if trade.id in market_data.exit_trades_ids:
                        market_data.exit_trades_ids.remove(trade.id)

    def process(self, strategy_trader: StrategyTrader):
        with self._mutex:
            if strategy_trader in self._need_update:
                self._need_update.remove(strategy_trader)
            else:
                return

        with self._mutex:
            # update handler
            market_data = self._markets.get(strategy_trader)

        if market_data is None:
            return

        with strategy_trader.trade_mutex:
            entry_trades = [None] * len(market_data.entry_trades_ids)
            exit_trades = [None] * len(market_data.exit_trades_ids)

            # retrieves the exits trades and the entry trades
            for trade in strategy_trader.trades:
                for i, tid in enumerate(market_data.entry_trades_ids):
                    if trade.id == tid:
                        entry_trades[i] = trade

                for j, tid in enumerate(market_data.exit_trades_ids):
                    if trade.id == tid:
                        exit_trades[j] = trade

            self._merge_trades(strategy_trader, market_data, entry_trades, exit_trades)

        with self._mutex:
            # update handler
            self._markets[strategy_trader] = market_data

    def dumps(self, strategy_trader: StrategyTrader) -> Dict[str, Union[str, int, float]]:
        results = super().dumps(strategy_trader)

        results.update({
            'num-take-profits': self._num_take_profits,
            'percentiles': ", ".join(["%s%%" % int(p) for p in self._percentiles]),
        })

        return results

    def _merge_trades(self, strategy_trader: StrategyTrader, market_data: DCAMarketData,
                      entry_trades: List[StrategyTrade], exits_trades: List[StrategyTrade]):

        entry_qty = 0.0
        entry_price = 0.0

        exit_qty = 0.0
        exit_prices = []

        need_update = False

        for trade in entry_trades:
            pending_qty = strategy_trader.instrument.adjust_quantity(trade.exec_entry_qty - trade.exec_exit_qty)
            entry_qty += pending_qty
            entry_price += trade.entry_price * pending_qty

        if entry_qty > 0:
            entry_price /= entry_qty

        if entry_qty != market_data.total_quantity:
            market_data.total_quantity = entry_qty
            need_update = True

        if entry_qty > 0 and not exits_trades:
            need_update = True

        if not need_update:
            # nothing to do
            return

        trader = strategy_trader.strategy.trader()

        # cancel entry trades
        for trade in entry_trades:
            try:
                trade.cancel_close(trader, strategy_trader.instrument)
                strategy_trader.remove_trade(trade)
            except Exception as e:
                error_logger.error(repr(e))

        # create/update exit trades
        # @todo recompute exits trades (price and quantity)

        # cancel exit trades
        for trade in exits_trades:
            try:
                trade.cancel_open(trader, strategy_trader.instrument)
                strategy_trader.remove_trade(trade)
            except Exception as e:
                error_logger.error(repr(e))

        market_data.exit_trades_ids = []

        # create new exits trades
        # @todo

        market_data.entry_trades_ids.clear()
