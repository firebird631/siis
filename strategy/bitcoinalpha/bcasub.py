# @date 2019-01-19
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Bitcoin Alpha strategy sub-strategy base class.

from instrument.candlegenerator import CandleGenerator
from strategy.timeframebasedsub import TimeframeBasedSub


class BitcoinAlphaStrategySub(TimeframeBasedSub):
    """
    Bitcoin Alpha sub computation.
    """

    def __init__(self, strategy_trader, params):
        super().__init__(strategy_trader, params['timeframe'], params['depth'], params['history'], params)

        # indicators
        for ind, param in params['indicators'].items():
            if param is not None:
                setattr(self, ind, self.strategy_trader.strategy.indicator(param[0])(self.tf, *param[1:]))
            else:
                setattr(self, ind, None)

        self.can_long = False
        self.can_short = False

        self.trend = 0
