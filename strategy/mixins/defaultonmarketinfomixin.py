# @date 2023-09-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Default implementation of on_market_info, mixin

from instrument.instrument import Instrument
from strategy.trade.strategyassettrade import StrategyAssetTrade
from strategy.trade.strategyindmargintrade import StrategyIndMarginTrade
from strategy.trade.strategymargintrade import StrategyMarginTrade
from strategy.trade.strategypositiontrade import StrategyPositionTrade

import logging

logger = logging.getLogger('siis.strategy.mixins.defaultmarketinfomixin')
error_logger = logging.getLogger('siis.error.strategy.mixins.defaultmarketinfomixin')
traceback_logger = logging.getLogger('siis.traceback.strategy.mixins.defaultmarketinfomixin')


class DefaultOnMarketInfoMixin(object):
    """
    Default implementation of on_market_info, mixin.
    """

    def on_market_info(self):
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
