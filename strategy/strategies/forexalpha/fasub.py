# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Forex Alpha strategy sub-strategy base class.

from strategy.indicator.score import Score
from strategy.timeframebasedsub import TimeframeBasedSub


class ForexAlphaStrategySub(TimeframeBasedSub):
    """
    Forex Alpha strategy sub-strategy base class.
    """

    def __init__(self, strategy_trader, params):
        self.rsi = None
        self.sma = None
        self.ema = None
        self.atr = None
        self.vwma = None
        self.sma200 = None
        self.sma55 = None
        self.bsawe = None
        self.stochrsi = None
        self.tomdemark = None
        self.bollingerbands = None
        self.pivotpoint = None

        super().__init__(strategy_trader, params['timeframe'], params['depth'], params['history'], params)

        self.score_ratio = params['score-ratio']
        self.score_level = params['score-level']

        self.score = Score(2, self.depth)

        self.setup_indicators(params)
