# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy, based on forex alpha.

import traceback

from datetime import datetime, timedelta
from terminal.terminal import Terminal

from common.utils import timeframe_to_str

from strategy.strategy import Strategy

from instrument.instrument import Instrument
from watcher.watcher import Watcher
from database.database import Database

from strategy.strategydatafeeder import StrategyDataFeeder

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
        return CryptoAlphaStrategyTrader(self, instrument, self.specific_parameters(instrument.market_id))

    def setup_live(self):
        super().setup_live()

        # pre-feed in live mode only
        Terminal.inst().info("In appliance %s retrieves last data history..." % self.name, view='status')

        now = datetime.now()

        for market_id, instrument in self._instruments.items():
            try:
                watcher = instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
                if watcher:
                    tfs = [(tf['timeframe'], tf['history']) for tf in self.timeframes_config.values() if tf['timeframe'] > 0]
                    watcher.subscribe(instrument.symbol, tfs)
                    
                    # query for most recent candles per timeframe
                    for k, timeframe in self.timeframes_config.items():
                        if timeframe['timeframe'] > 0:
                            l_from = now - timedelta(seconds=timeframe['history']*timeframe['timeframe'])
                            l_to = now
                            watcher.historical_data(instrument.symbol, timeframe['timeframe'], from_date=l_from, to_date=l_to)

                            # wait for this timeframe before processing
                            instrument.want_timeframe(timeframe['timeframe'])

            except Exception as e:
                logger.error(repr(e))
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
