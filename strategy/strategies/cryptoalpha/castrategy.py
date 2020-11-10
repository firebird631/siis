# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy, based on forex alpha.

from strategy.strategy import Strategy

from .castrategytrader import CryptoAlphaStrategyTrader
from .caparameters2 import DEFAULT_PARAMS


class CryptoAlphaStrategy(Strategy):
    """
    CryptoAlpha strategy.
    Dedicated to crypto major or alt-coin for asset only (buy/sell), no margin, no short.
    """

    def __init__(self, strategy_service, watcher_service, trader_service, options, user_parameters):
        super().__init__("cryptoalpha", strategy_service, watcher_service, trader_service, options, DEFAULT_PARAMS, user_parameters)

        self.reset()

    def reset(self):
        super().reset()

        # timeframe parameters
        self.timeframes_config = self.parameters['timeframes']

    def create_trader(self, instrument):
        return CryptoAlphaStrategyTrader(self, instrument, self.specific_parameters(instrument.market_id))
