# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy sub-strategy base class.

from strategy.strategytimeframeanalyser import StrategyTimeframeAnalyser


class CryptoAlphaAnalyser(StrategyTimeframeAnalyser):
    """
    CryptoAlpha sub computation.
    """

    def __init__(self, name: str, strategy_trader, params: dict):
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

        super().__init__(name, strategy_trader, params['timeframe'], params['depth'], params['history'], params)

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
