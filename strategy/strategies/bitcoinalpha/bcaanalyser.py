# @date 2019-01-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Bitcoin Alpha strategy sub-strategy base class.

from strategy.strategytimeframeanalyser import StrategyTimeframeAnalyser


class BitcoinAlphaAnalyser(StrategyTimeframeAnalyser):
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

        self.mama_cross = (0, 0.0, 0.0)

        super().__init__(strategy_trader, params['timeframe'], params['depth'], params['history'], params)

        self.setup_indicators(params)

        self.can_long = False
        self.can_short = False

        self.trend = 0

        self._signal_at_close = params.get('signal-at-close', False)
        self.last_signal = None

    @property
    def signal_at_close(self) -> bool:
        return self._signal_at_close

    def need_signal(self, timestamp: float) -> bool:
        if self._signal_at_close:
            return self._last_closed

        return True
