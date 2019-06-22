# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy sub-strategy base class.

from instrument.candlegenerator import CandleGenerator
from strategy.timeframebasedsub import TimeframeBasedSub


class CryptoAlphaStrategySub(TimeframeBasedSub):
    """
    CryptoAlpha sub computation.
    """

    def __init__(self, data, params):
        super().__init__(data, params['timeframe'], params['parent'], params['depth'], params['history'])

        # indicators
        for ind, param in params['indicators'].items():
            if param is not None:
                setattr(self, ind, self.data.strategy.indicator(param[0])(self.tf, *param[1:]))
            else:
                setattr(self, ind, None)
