# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Forex Alpha strategy sub-strategy base class.

from strategy.indicator.score import Score
from strategy.strategytimeframeanalyser import StrategyTimeframeAnalyser


class ForexAlphaAnalyser(StrategyTimeframeAnalyser):
    """
    Forex Alpha strategy sub-strategy base class.
    """

    def __init__(self, name: str, strategy_trader, params: dict):
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

        super().__init__(name, strategy_trader, params['timeframe'], params['depth'], params['history'], params)

        self.score_ratio = params['score-ratio']
        self.score_level = params['score-level']

        self.score = Score(2, self.depth)

        self._signal_at_close = params.get('signal-at-close', False)
        self.last_signal = None

        self.setup_indicators(params)

    @property
    def signal_at_close(self) -> bool:
        return self._signal_at_close

    def need_signal(self, timestamp: float) -> bool:
        if self._signal_at_close:
            return self._last_closed

        return True
