# @date 2019-01-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Crystal Ball strategy, based on bsawe+td9 indicators

from strategy.strategy import Strategy

from strategy.strategydatafeeder import StrategyDataFeeder

from .cbstrategytrader import CrystalBallStrategyTrader
from .cbparameters import DEFAULT_PARAMS


class CrystalBallStrategy(Strategy):
    """
    Crystal ball strategy indicator.
    Pure alert indicator only. No trading.
    """

    def __init__(self, strategy_service, watcher_service, trader_service, options, parameters):
        super().__init__("crystalball", strategy_service, watcher_service, trader_service, options, DEFAULT_PARAMS)

        if parameters:
            # apply overrided parameters
            self._parameters.update(parameters)

        self.reset()

    def reset(self):
        super().reset()

        # reversal mode is default, else need to define how to prefer entry or exit
        self.reversal = self.parameters['reversal']

        # timeframe parameters
        self.timeframes_config = self.parameters['timeframes']

    def create_trader(self, instrument):
        return CrystalBallStrategyTrader(self, instrument, self.specific_parameters(instrument.market_id))
