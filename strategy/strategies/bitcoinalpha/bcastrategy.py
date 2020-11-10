# @date 2019-01-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Bitcoin Alpha strategy, based on crypto alpha with short additionnal and margin trading

from strategy.strategy import Strategy

from .bcastrategytrader import BitcoinAlphaStrategyTrader
from .bcaparameters import DEFAULT_PARAMS


class BitcoinAlphaStrategy(Strategy):
    """
    BitcoinAlpha strategy.
    Dedicaded to top 3 crypto in margin trading (long/short).
    """

    def __init__(self, strategy_service, watcher_service, trader_service, options, user_parameters):
        super().__init__("bitcoinalpha", strategy_service, watcher_service, trader_service, options, DEFAULT_PARAMS, user_parameters)

        self.reset()

    def reset(self):
        super().reset()

        # reversal mode is default, else need to define how to prefer entry or exit
        self.reversal = self.parameters['reversal']

        # timeframe parameters
        self.timeframes_config = self.parameters['timeframes']

    def create_trader(self, instrument):
        return BitcoinAlphaStrategyTrader(self, instrument, self.specific_parameters(instrument.market_id))
