# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy alpha processor.

import os
import time
import collections
import traceback

from datetime import datetime, timedelta

from common.utils import timeframe_to_str, timeframe_from_str, UTC

from common.signal import Signal
from instrument.instrument import Instrument

from watcher.watcher import Watcher

from strategy.indicator.models import Limits
from strategy.strategydatafeeder import StrategyDataFeeder

from database.database import Database

import logging
logger = logging.getLogger('siis.strategy.process.alpha')
error_logger = logging.getLogger('siis.error.strategy.process.alpha')
traceback_logger = logging.getLogger('siis.traceback.strategy.process.alpha')


def setup_process(strategy):
    """
    Setup this alpha processing to the strategy.
    Setup for live and backtesting are OHLCs history, and process trade/tick data for backtesting.
    There is a bootstrap processing before going to live or to receive backtest data.
    """
    strategy._setup_backtest = alpha_setup_backtest
    strategy._setup_live = alpha_setup_live

    strategy._update_strategy = alpha_update_strategy
    strategy._async_update_strategy = alpha_async_update_strategy


def alpha_bootstrap(strategy, strategy_trader):
    """
    Process the bootstrap of the strategy trader until complete using the preloaded OHLCs.
    Any received updates are ignored until the bootstrap is completed.
    """
    if strategy_trader._bootstraping == 2:
        # in progress
        return

    # bootstraping in progress, avoid live until complete
    strategy_trader._bootstraping = 2

    try:
        if strategy_trader.is_timeframes_based:
            timeframe_based_bootstrap(strategy, strategy_trader)
        elif strategy_trader.is_tickbars_based:
            tickbar_based_bootstrap(strategy, strategy_trader)
    except Exception as e:
        error_logger.error(repr(e))
        traceback_logger.error(traceback.format_exc())

    # bootstraping done, can now branch to live
    strategy_trader._bootstraping = 0


def timeframe_based_bootstrap(strategy, strategy_trader):
    # captures all initials candles
    initial_candles = {}

    # compute the begining timestamp
    timestamp = strategy.timestamp

    instrument = strategy_trader.instrument

    for tf, sub in strategy_trader.timeframes.items():
        candles = instrument.candles(tf)
        initial_candles[tf] = candles

        # reset, distribute one at time
        instrument._candles[tf] = []

        if candles:
            # get the nearest next candle
            timestamp = min(timestamp, candles[0].timestamp + sub.depth*sub.timeframe)

    logger.debug("%s timeframes bootstrap begin at %s, now is %s" % (instrument.market_id, timestamp, strategy.timestamp))

    # initials candles
    lower_timeframe = 0

    for tf, sub in strategy_trader.timeframes.items():
        candles = initial_candles[tf]

        # feed with the initials candles
        while candles and timestamp >= candles[0].timestamp:
            candle = candles.pop(0)

            instrument._candles[tf].append(candle)

            # and last is closed
            sub._last_closed = True

            # keep safe size
            if(len(instrument._candles[tf])) > sub.depth:
                instrument._candles[tf].pop(0)

            # prev and last price according to the lower timeframe close
            if not lower_timeframe or tf < lower_timeframe:
                lower_timeframe = tf
                strategy_trader.prev_price = strategy_trader.last_price
                strategy_trader.last_price = candle.close  # last mid close

    # process one lowest candle at time
    while 1:
        num_candles = 0
        strategy_trader.bootstrap(timestamp)

        # at least of lower timeframe
        base_timestamp = 0.0
        lower_timeframe = 0

        # increment by the lower available timeframe
        for tf, sub in strategy_trader.timeframes.items():
            if initial_candles[tf]:
                if not base_timestamp:
                    # initiate with the first
                    base_timestamp = initial_candles[tf][0].timestamp

                elif initial_candles[tf][0].timestamp < base_timestamp:
                    # found a lower
                    base_timestamp = initial_candles[tf][0].timestamp

        for tf, sub in strategy_trader.timeframes.items():
            candles = initial_candles[tf]

            # feed with the next candle
            if candles and base_timestamp >= candles[0].timestamp:
                candle = candles.pop(0)

                instrument._candles[tf].append(candle)

                # and last is closed
                sub._last_closed = True

                # keep safe size
                if(len(instrument._candles[tf])) > sub.depth:
                    instrument._candles[tf].pop(0)

                if not lower_timeframe or tf < lower_timeframe:
                    lower_timeframe = tf
                    strategy_trader.prev_price = strategy_trader.last_price
                    strategy_trader.last_price = candle.close  # last mid close

                num_candles += 1

        # logger.info("next is %s (delta=%s) / now %s (n=%i) (low=%s)" % (base_timestamp, base_timestamp-timestamp, strategy.timestamp, num_candles, lower_timeframe))
        timestamp = base_timestamp

        if not num_candles:
            # no more candles to process
            break

    logger.debug("%s timeframes bootstraping done" % instrument.market_id)


def tickbar_based_bootstrap(strategy, strategy_trader):
    # captures all initials ticks
    initial_ticks = []

    # compute the begining timestamp
    timestamp = strategy.timestamp

    instrument = strategy_trader.instrument

    logger.debug("%s tickbars bootstrap begin at %s, now is %s" % (instrument.market_id, timestamp, strategy.timestamp))

    # @todo need tickstreamer, and call strategy_trader.bootstrap(timestamp) at per bulk of ticks (temporal size defined)

    logger.debug("%s tickbars bootstraping done" % instrument.market_id)


def alpha_update_strategy(strategy, strategy_trader):
    """
    Compute a strategy step per instrument.
    Default implementation supports bootstrapping.
    @param strategy_trader StrategyTrader Instance of the strategy trader to process.
    @note Non thread-safe method.
    """
    if strategy_trader:
        if not strategy_trader._initialized:
            initiate_strategy_trader(strategy, strategy_trader)
            return

        if not strategy_trader.instrument.ready():
            # process only if instrument has data
            return

        if not strategy_trader._checked:
            # need to check existings trade orders, trade history and positions
            strategy_trader.check_trades(strategy.timestamp)

        if strategy_trader._processing:
            # process only if previous job was completed
            return

        try:
            strategy_trader._processing = True

            if strategy_trader._bootstraping > 0:
                # first : bootstrap using preloaded data history
                alpha_bootstrap(strategy, strategy_trader)

            else:
                # then : until process instrument update
                strategy_trader.process(strategy.timestamp)

        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

        finally:
            # process complete
            strategy_trader._processing = False


def alpha_async_update_strategy(strategy, strategy_trader):
    """
    Override this method to compute a strategy step per instrument.
    Default implementation supports bootstrapping.
    @param strategy_trader StrategyTrader Instance of the strategy trader to process.
    @note Thread-safe method.
    """
    if strategy_trader:
        if not strategy_trader._initialized:
            initiate_strategy_trader(strategy, strategy_trader)
            return

        if strategy_trader.instrument.ready():
            # process only if previous job was completed
            process = False

            with strategy_trader._mutex:
                if not strategy_trader._processing:
                    # can process
                    process = strategy_trader._processing = True

            if process:
                if strategy_trader._bootstraping > 0:
                    # second : bootstrap using preloaded data history
                    alpha_bootstrap(strategy, strategy_trader)

                else:
                    # then : until process instrument update
                    strategy_trader.process(strategy.timestamp)

                with strategy_trader._mutex:
                    # process complete
                    strategy_trader._processing = False


def initiate_strategy_trader(strategy, strategy_trader):
    """
    Do it async into the workers to avoid long blocking of the strategy thread.
    """
    now = datetime.now()

    instrument = strategy_trader.instrument
    try:
        watcher = instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
        if watcher:
            tfs = {tf['timeframe']: tf['history'] for tf in strategy.parameters.get('timeframes', {}).values() if tf['timeframe'] > 0}
            watcher.subscribe(instrument.market_id, tfs, None, None)

            # query for most recent candles per timeframe
            for k, timeframe in strategy.parameters.get('timeframes', {}).items():
                if timeframe['timeframe'] > 0:
                    l_from = now - timedelta(seconds=timeframe['history']*timeframe['timeframe'])
                    l_to = now

                    # wait for this timeframe before processing
                    instrument.want_timeframe(timeframe['timeframe'])

                    # fetch database
                    watcher.historical_data(instrument.market_id, timeframe['timeframe'], from_date=l_from, to_date=l_to)

            # initialization processed, waiting for data be ready
            strategy_trader._initialized = True

    except Exception as e:
        logger.error(repr(e))
        logger.debug(traceback.format_exc())


#
# backtesting setup
#

def alpha_setup_backtest(strategy, from_date, to_date, base_timeframe=Instrument.TF_TICK):
    """
    Simple load history of OHLCs, initialize all strategy traders here (sync).
    """
    for market_id, instrument in strategy._instruments.items():
        # retrieve the related price and volume watcher
        watcher = instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
        if watcher:
            # query an history of candles per timeframe
            for k, timeframe in strategy.parameters.get('timeframes', {}).items():
                if timeframe['timeframe'] > 0:
                    # preload some previous candles
                    l_from = from_date - timedelta(seconds=timeframe['history']*timeframe['timeframe'])
                    l_to = from_date - timedelta(seconds=1)
                    watcher.historical_data(instrument.market_id, timeframe['timeframe'], from_date=l_from, to_date=l_to)

                    # wait for this timeframe before processing
                    instrument.want_timeframe(timeframe['timeframe'])

            # create a feeder per instrument and fetch ticks and candles + ticks
            feeder = StrategyDataFeeder(strategy, instrument.market_id, [], True)
            strategy.add_feeder(feeder)

            # fetch market info from the DB
            Database.inst().load_market_info(strategy.service, watcher.name, instrument.market_id)

            feeder.initialize(watcher.name, from_date, to_date)

    # initialized state
    for k, strategy_trader in strategy._strategy_traders.items():
        strategy_traders._initialized = True


#
# live setup
#

def alpha_setup_live(strategy):
    """
    Do it here dataset preload and other stuff before update be called.
    """
    logger.info("In strategy %s retrieves states and previous trades..." % strategy.name)

    # load the strategy-traders and traders for this strategy/account
    trader = strategy.trader()

    Database.inst().load_user_trades(strategy.service, strategy, trader.name,
            trader.account.name, strategy.identifier)

    Database.inst().load_user_traders(strategy.service, strategy, trader.name,
            trader.account.name, strategy.identifier)

    for market_id, instrument in strategy._instruments.items():
        # wake-up all for initialization
        strategy.send_initialize_strategy_trader(market_id)

    logger.info("Strategy %s data retrieved" % strategy.name)
