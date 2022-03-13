# @date 2019-01-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Bitcoin Alpha strategy sub-strategy base class.

from strategy.timeframebasedsub import TimeframeBasedSub


class BitcoinAlphaStrategySub(TimeframeBasedSub):
    """
    Bitcoin Alpha sub computation.
    """

    def __init__(self, strategy_trader, params):
        self.sma = None
        self.ema = None
        self.rsi = None
        self.stochrsi = None
        self.tomdemark = None
        self.score = None
        self.sma200 = None
        self.sma55 = None
        self.bollingerbands = None
        self.bswave = None
        self.atr = None
        self.bsawe = None
        self.mama = None
        self.pivotpoint = None

        super().__init__(strategy_trader, params['timeframe'], params['depth'], params['history'], params)

        self.setup_indicators(params)

        self.can_long = False
        self.can_short = False

        self.trend = 0
