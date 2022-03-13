# @date 2019-01-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Crystal Ball strategy sub-strategy base class.

from strategy.timeframebasedsub import TimeframeBasedSub


class CrystalBallStrategySub(TimeframeBasedSub):
    """
    Bitcoin Alpha sub computation.
    """

    def __init__(self, strategy_trader, params):
        super().__init__(strategy_trader, params['timeframe'], params['depth'], params['history'], params)

        self.setup_indicators(params)
