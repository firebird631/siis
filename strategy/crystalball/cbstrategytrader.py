# @date 2019-01-19
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Crystal Ball indicator strategy trader.

from strategy.timeframebasedstrategytrader import TimeframeBasedStrategyTrader
from strategy.strategyindmargintrade import StrategyIndMarginTrade
from strategy.strategysignal import StrategySignal

from instrument.instrument import Instrument

from strategy.indicator import utils
from strategy.indicator.score import Score

from common.utils import timeframe_to_str

from .cbsuba import CrystalBallStrategySubA
from .cbparameters import DEFAULT_PARAMS

import logging
logger = logging.getLogger('siis.strategy.crystalball')


class CrystalBallStrategyTrader(TimeframeBasedStrategyTrader):
    """
    Crystal Ball indicator strategy trader.
    """

    def __init__(self, strategy, instrument, params):
        super().__init__(strategy, instrument, params['base-timeframe'])

        # mean when there is already a position on the same direction does not increase in the same direction if 0 or increase at max N times
        self.pyramided = params['pyramided']
        self.max_trades = params['max-trades']

        self.min_price = params['min-price']
        self.min_vol24h = params['min-vol24h']

        self.min_traded_timeframe = self.timeframe_from_param(params.get('min-traded-timeframe', "15m"))
        self.max_traded_timeframe = self.timeframe_from_param(params.get('max-traded-timeframe', "4h"))

        # @todo remove and prefers overrided default parameters once done
        # if self.strategy.identifier == "binance-crystalball":
        #     self.min_traded_timeframe = Instrument.TF_5MIN

        for k, timeframe in strategy.timeframes_config.items():
            if timeframe['mode'] == 'A':
                sub = CrystalBallStrategySubA(self, timeframe)
                self.timeframes[timeframe['timeframe']] = sub
            else:
                continue

        self._last_filter_cache = (0, False, False)

        self.setup_streaming()

    def filter_market(self, timestamp):
        """
        The first boolean mean accept, the second compute.
        Return True, True if the market is accepted and can be computed this time.
        """
        if timestamp - self._last_filter_cache[0] < 60*60:  # only once per hour
            return self._last_filter_cache[1], self._last_filter_cache[2]
        
        trader = self.strategy.trader()

        if not trader:
            self._last_filter_cache = (timestamp, False, False)
            return False, False

        market = trader.market(self.instrument.market_id)

        if not market:
            self._last_filter_cache = (timestamp, False, False)
            return False, False

        # if there is no actives trades we can avoid computation on some ininteresting markets
        if self.trades:
            if market.vol24h_quote is not None and market.vol24h_quote < self.min_vol24h:
                # accepted but 24h volume is very small (rare possibilities of exit)
                self._last_filter_cache = (timestamp, True, False)
                return True, False

        self._last_filter_cache = (timestamp, True, True)
        return True, True

    def process(self, timeframe, timestamp):
        # process only at base timeframe
        if timeframe != self.base_timeframe:
            return

        # update data at tick level
        if timeframe == self.base_timeframe:
            self.gen_candles_from_ticks(timestamp)

        accept, compute = self.filter_market(timestamp)
        if not accept:
            return

        # and compute
        entries = []
        exits = []

        if compute:
            entries, exits = self.compute(timeframe, timestamp)

        trader = self.strategy.trader()

        if not trader:
            self._last_filter_cache = (timestamp, False, False)
            return False, False

        market = trader.market(self.instrument.market_id)

        for entry in entries:
            self.strategy.notify_order(-1, entry.direction, self.instrument.market_id,
                            market.format_price(entry.price), timestamp, entry.timeframe, 'entry',
                            None, market.format_price(entry.sl), market.format_price(entry.tp))

        for exit in exits:
            self.strategy.notify_order(-1, exit.direction, self.instrument.market_id,
                            market.format_price(exit.price), timestamp, exit.timeframe, 'exit')

        # update user managed actives trades
        self.update_trades(timestamp)
