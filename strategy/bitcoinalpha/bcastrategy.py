# @date 2019-01-19
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Bitcoin Alpha strategy, based on crypto alpha with short additionnal and margin trading

import traceback

from datetime import datetime, timedelta
from terminal.terminal import Terminal

from config import config

from strategy.strategy import Strategy

from instrument.instrument import Instrument
from watcher.watcher import Watcher
from database.database import Database

from strategy.indicator import utils
from strategy.indicator.score import Score, Scorify
from strategy.strategydatafeeder import StrategyDataFeeder

from .bcastrategytrader import BitcoinAlphaStrategyTrader
from .bcaparameters import DEFAULT_PARAMS

import logging
logger = logging.getLogger('siis.strategy.bitcoinalpha')


class BitcoinAlphaStrategy(Strategy):
    """
    BitcoinAlpha strategy.
    Dedicaded to top 3 crypto in margin trading (long/short).
    """

    def __init__(self, strategy_service, watcher_service, trader_service, options, parameters):
        super().__init__("bitcoinalpha", strategy_service, watcher_service, trader_service, options, DEFAULT_PARAMS)

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

    def start(self):
        if super().start():
            # reset data
            self.reset()

            # listen to watchers and strategy signals
            self.watcher_service.add_listener(self)
            self.service.add_listener(self)

            return True
        else:
            return False

    def stop(self):
        super().stop()

        # rest data
        self.reset()

    def create_trader(self, instrument):
        return BitcoinAlphaStrategyTrader(self, instrument, self.parameters)

    def update_strategy(self, tf, instrument):
        sub_trader = self._sub_traders.get(instrument)
        if sub_trader:
            # and process instrument update
            sub_trader.process(tf, self.timestamp)

    def setup_live(self):
        # pre-feed in live mode only
        Terminal.inst().info("In appliance %s retrieves last data history..." % self.name, view='status')

        now = datetime.now()

        for market_id, instrument in self._instruments.items():
            try:
                watcher = instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
                if watcher:
                    # query for most recent candles per timeframe
                    for k, timeframe in self.timeframes_config.items():
                        if timeframe['timeframe'] > 0:
                            l_from = now - timedelta(seconds=timeframe['history']*timeframe['timeframe'])
                            l_to = now
                            watcher.historical_data(instrument.symbol, timeframe['timeframe'], from_date=l_from, to_date=l_to)

                            # wait for this timeframe before processing
                            instrument.want_timeframe(timeframe['timeframe'])

            except Exception as e:
                logger.error(repr(e), True)
                logger.debug(traceback.format_exc())

        Terminal.inst().info("Appliance data retrieved", view='status')

    def setup_backtest(self, from_date, to_date):
        trader = self.trader()

        # preload data for any supported instruments
        for market_id, instrument in self._instruments.items():
            # retrieve the related price and volume watcher
            watcher = instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
            if watcher:
                # query an history of candles per timeframe
                for k, timeframe in self.timeframes_config.items():
                    if timeframe['timeframe'] > 0:
                        # preload some previous candles
                        l_from = from_date - timedelta(seconds=timeframe['history']*timeframe['timeframe'])
                        l_to = from_date - timedelta(seconds=1)
                        watcher.historical_data(instrument.symbol, timeframe['timeframe'], from_date=l_from, to_date=l_to)

                        # wait for this timeframe before processing
                        instrument.want_timeframe(timeframe['timeframe'])

            # create a feeder per instrument and fetch ticks and candles + ticks
            feeder = StrategyDataFeeder(self, instrument.market_id, [], True)
            self.add_feeder(feeder)

            # fetch market info from the DB
            Database.inst().load_market_info(self.service, watcher.name, instrument.market_id)

            feeder.initialize(watcher.name, from_date, to_date)
