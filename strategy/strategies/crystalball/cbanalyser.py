# @date 2019-01-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Crystal Ball strategy sub-strategy base class.

from strategy.strategytimeframeanalyser import StrategyTimeframeAnalyser


class CrystalBallAnalyser(StrategyTimeframeAnalyser):
    """
    Bitcoin Alpha sub computation.
    """

    def __init__(self, strategy_trader, params):
        super().__init__(strategy_trader, params['timeframe'], params['depth'], params['history'], params)

        self.setup_indicators(params)

        self._signal_at_close = params.get('signal-at-close', False)
        self.last_signal = None

    @property
    def signal_at_close(self) -> bool:
        return self._signal_at_close

    def need_signal(self, timestamp: float) -> bool:
        if self._signal_at_close:
            return self._last_closed

        return True
