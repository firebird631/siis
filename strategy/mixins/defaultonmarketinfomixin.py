# @date 2023-09-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Default implementation of on_market_info, mixin

from typing import Union

from strategy.strategysignal import StrategySignal
from strategy.strategytraderbase import StrategyTraderBase

from strategy.trade.strategyassettrade import StrategyAssetTrade
from strategy.trade.strategyindmargintrade import StrategyIndMarginTrade
from strategy.trade.strategymargintrade import StrategyMarginTrade
from strategy.trade.strategypositiontrade import StrategyPositionTrade

from instrument.instrument import Instrument
from strategy.strategy import Strategy

import logging

logger = logging.getLogger('siis.strategy.mixins.defaultmarketinfomixin')
error_logger = logging.getLogger('siis.error.strategy.mixins.defaultmarketinfomixin')
traceback_logger = logging.getLogger('siis.traceback.strategy.mixins.defaultmarketinfomixin')


class DefaultOnMarketInfoMixin(object):
    """
    Default implementation of on_market_info, mixin.
    """
    def __init__(self, strategy: Strategy, instrument: Instrument, base_timeframe: float, params: dict):
        super().__init__(strategy, instrument, base_timeframe, params)

        self.trade_type = StrategyTraderBase.TRADE_TYPE_MAP.get(
            params.get('trade-type', 'asset'), Instrument.TRADE_SPOT)

        self.trade_clazz = None

    def on_market_info(self  # type: Union[DefaultOnMarketInfoMixin, StrategyTraderBase]
                       ):
        super().on_market_info()

        # instantiate market type
        if not self.trade_clazz:
            if self.trade_type == Instrument.TRADE_SPOT and self.instrument.has_spot:
                self.trade_clazz = StrategyAssetTrade
                self._trade_short = False
                logger.info("Market type using asset trade for %s" % self.instrument.market_id)

            elif (self.trade_type == Instrument.TRADE_POSITION and self.instrument.has_margin and
                  self.instrument.has_position and not self.instrument.indivisible_position):

                self.trade_clazz = StrategyPositionTrade
                self._trade_short = True
                logger.info("Market type using position trade for %s" % self.instrument.market_id)

            elif (self.trade_type == Instrument.TRADE_MARGIN and self.instrument.has_margin and
                  not self.instrument.indivisible_position):

                self.trade_clazz = StrategyMarginTrade
                self._trade_short = True
                logger.info("Market type using margin trade for %s" % self.instrument.market_id)

            elif (self.trade_type == Instrument.TRADE_IND_MARGIN and self.instrument.has_margin and
                  self.instrument.indivisible_position):

                self.trade_clazz = StrategyIndMarginTrade
                self._trade_short = True
                logger.info("Market type using indivisible margin trade for %s" % self.instrument.market_id)

            else:
                logger.warning("Market type is not compatible for %s" % self.instrument.market_id)

    def compute_contexts_signals(self,  # type: Union[DefaultOnMarketInfoMixin, StrategyTraderBase]
                                 timestamp: float, prev_price: float, last_price: float):
        """
        Simple implementation that compute and filters entry signals from any compiled contexts.
        @param timestamp: Current timestamp
        @param prev_price: Previous last_price price
        @param last_price: Last market traded price
        @return: A strategy signal or None
        """
        last_signal = None

        for ctx in self._trade_contexts.values():
            # process each compiled and valid context
            ctx.update(timestamp)

            signal = ctx.compute_signal(self.instrument, timestamp, prev_price, last_price)

            # check for a valid signal
            if signal and self.trade_clazz and signal.check():
                # defines the configured quantity if missing
                if not signal.quantity:
                    if self.trade_clazz.is_spot():
                        # quantity from instrument in quote size
                        signal.quantity = self.instrument.trade_quantity
                    elif self.trade_clazz.is_margin():
                        # quantity from instrument in contract or quote to base
                        signal.quantity = max(self.instrument.min_notional, self.instrument.trade_quantity)

                # filter only entry signal
                if signal.signal == StrategySignal.SIGNAL_ENTRY:
                    last_signal = signal

        # finalize, clear states
        self.cleanup_analyser(timestamp)

        return last_signal
