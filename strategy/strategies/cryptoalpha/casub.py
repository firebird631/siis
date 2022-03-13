# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy sub-strategy base class.

from strategy.timeframebasedsub import TimeframeBasedSub


class CryptoAlphaStrategySub(TimeframeBasedSub):
    """
    CryptoAlpha sub computation.
    """

    def __init__(self, strategy_trader, params):
        self.rsi = None
        self.sma = None
        self.ema = None
        self.stochrsi = None
        self.tomdemark = None
        self.bollingerbands = None
        self.bsawe = None
        self.sma55 = None
        self.sma200 = None
        self.atr = None
        self.mama = None
        self.pivotpoint = None

        super().__init__(strategy_trader, params['timeframe'], params['depth'], params['history'], params)

        self.setup_indicators(params)

        self.can_long = False
        self.can_short = False

        self.trend = 0
