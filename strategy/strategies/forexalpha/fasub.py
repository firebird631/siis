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
        super().__init__(strategy_trader, params['timeframe'], params['depth'], params['history'], params)

        self.score_ratio = params['score-ratio']
        self.score_level = params['score-level']

        self.score = Score(2, self.depth)

        self.setup_indicators(params)
