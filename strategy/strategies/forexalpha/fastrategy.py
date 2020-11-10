# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Forex Alpha strategy

from strategy.strategy import Strategy

from .fastrategytrader import ForexAlphaStrategyTrader
from .faparameters import DEFAULT_PARAMS


class ForexAlphaStrategy(Strategy):
    """
    ForexAlpha strategy.

    - Work with market order
    - Stop are at market

    @todo Implement with a LIMIT (maker/taker) and a LIMIT (maker only) versions.
    """

    def __init__(self, strategy_service, watcher_service, trader_service, options, user_parameters):
        super().__init__("forexalpha", strategy_service, watcher_service, trader_service, options, DEFAULT_PARAMS, user_parameters)

        self.reset()

    def reset(self):
        super().reset()

        # timeframe parameters
        self.timeframes_config = self.parameters['timeframes']

    def create_trader(self, instrument):
        return ForexAlphaStrategyTrader(self, instrument, self.specific_parameters(instrument.market_id))
