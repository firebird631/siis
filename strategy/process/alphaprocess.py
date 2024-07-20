# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy alpha processor. This is the standard implementation.

import time
import traceback

from datetime import datetime, timedelta

from common.utils import UTC
from instrument.instrument import Instrument

from watcher.watcher import Watcher

from strategy.strategydatafeeder import StrategyDataFeeder

from database.database import Database

import logging
logger = logging.getLogger('siis.strategy.process.alpha')
error_logger = logging.getLogger('siis.error.strategy.process.alpha')
traceback_logger = logging.getLogger('siis.traceback.strategy.process.alpha')


def setup_process(strategy):
    """
    Setup this alpha processing to the strategy.
    Setup for live and backtesting.
    Support OHLC history (planned non-temporal Bar and Volume Profile history) and process
     and process trade/tick data for backtesting.
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
    with strategy_trader.mutex:
        if strategy_trader.bootstrapping != strategy_trader.STATE_WAITING:
            # only if waiting for bootstrapping
            return

        # bootstrapping in progress, suspend live until complete
        strategy_trader.set_bootstrapping(strategy_trader.STATE_PROGRESSING)

    try:
        if strategy_trader.is_timeframes_based:
            timeframe_based_bootstrap(strategy, strategy_trader)
        elif strategy_trader.is_tickbars_based:
            tickbar_based_bootstrap(strategy, strategy_trader)
    except Exception as e:
        error_logger.error(repr(e))
        traceback_logger.error(traceback.format_exc())

    with strategy_trader.mutex:
        # bootstrapping done, can now branch to live
        strategy_trader.set_bootstrapping(strategy_trader.STATE_NORMAL)


def timeframe_based_bootstrap(strategy, strategy_trader):
    # captures all initials candles
    initial_candles = {}

    # compute the beginning timestamp
    timestamp = strategy.timestamp
    instrument = strategy_trader.instrument

    for analyser in strategy_trader.analysers():
        candles = analyser.get_bars()
        initial_candles[analyser.name] = candles

        # reset, distribute one at time
        analyser.clear_bars()

        if candles:
            # get the nearest next candle
            timestamp = min(timestamp, candles[0].timestamp + analyser.depth*analyser.timeframe)

    logger.debug("%s timeframes bootstrap begin at %s, now is %s" % (
        instrument.market_id, timestamp, strategy.timestamp))

    # initials candles
    lower_timeframe = 0

    for analyser in strategy_trader.analysers():
        candles = initial_candles[analyser.name]

        # feed with the initials candles
        while candles and timestamp >= candles[0].timestamp:
            candle = candles.pop(0)

            analyser.add_bar(candle, analyser.history)

            # and last is closed
            analyser._last_closed = True

            # prev and last price according to the lower timeframe close
            if not lower_timeframe or analyser.timeframe < lower_timeframe:
                lower_timeframe = analyser.timeframe

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
        for analyser in strategy_trader.analysers():
            candles = initial_candles[analyser.name]
            if candles:
                if not base_timestamp:
                    # initiate with the first
                    base_timestamp = candles[0].timestamp

                elif candles[0].timestamp < base_timestamp:
                    # found a lower
                    base_timestamp = candles[0].timestamp

        # feed with the next candle
        for analyser in strategy_trader.analysers():
            candles = initial_candles[analyser.name]
            if candles and base_timestamp >= candles[0].timestamp:
                candle = candles.pop(0)

                analyser.add_bar(candle, analyser.history)

                # and last is closed
                analyser._last_closed = True

                if not lower_timeframe or analyser.timeframe < lower_timeframe:
                    lower_timeframe = analyser.timeframe

                    strategy_trader.prev_price = strategy_trader.last_price
                    strategy_trader.last_price = candle.close  # last mid close

                num_candles += 1

        # logger.info("next is %s (delta=%s) / now %s (n=%i) (low=%s)" % (base_timestamp, base_timestamp-timestamp, strategy.timestamp, num_candles, lower_timeframe))
        timestamp = base_timestamp

        if not num_candles:
            # no more candles to process
            break

    logger.debug("%s timeframes bootstrapping done" % instrument.market_id)


def tickbar_based_bootstrap(strategy, strategy_trader):
    # captures all initials ticks
    initial_ticks = []

    # compute the beginning timestamp
    timestamp = strategy.timestamp

    instrument = strategy_trader.instrument

    logger.debug("%s tickbars bootstrap begin at %s, now is %s" % (instrument.market_id, timestamp, strategy.timestamp))

    # @todo

    logger.debug("%s tickbars bootstrapping done" % instrument.market_id)


def alpha_update_strategy(strategy, strategy_trader, timestamp: float):
    """
    Compute a strategy step per instrument.
    Default implementation supports bootstrapping.
    @param strategy:
    @param strategy_trader StrategyTrader Instance of the strategy trader to process.
    @param timestamp: last traded tick or candle timestamp (can be slightly different from strategy timestamp)
    @note Non thread-safe method.
    """
    if strategy_trader:
        if strategy_trader.initialized == strategy_trader.STATE_WAITING:
            initiate_strategy_trader(strategy, strategy_trader)

        if strategy_trader.checked == strategy_trader.STATE_WAITING:
            # need to check existing trade orders, trade history and positions
            strategy_trader.check_trades(strategy.timestamp)

        if (strategy_trader.initialized != strategy_trader.STATE_NORMAL or
                strategy_trader.checked != strategy_trader.STATE_NORMAL or
                not strategy_trader.ready()):
            # process only if data are received and trades checked
            return

        if strategy_trader.processing:
            # process only if previous job was completed
            return

        try:
            strategy_trader.set_processing(True)

            if strategy_trader.bootstrapping == strategy_trader.STATE_WAITING:
                # first : bootstrap using preloaded data history
                alpha_bootstrap(strategy, strategy_trader)
            else:
                # then : until process instrument update
                strategy_trader.update_time_deviation(timestamp)

                if strategy.service.backtesting:
                    strategy_trader.process(timestamp)
                else:
                    strategy_trader.process(timestamp)

        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())
        finally:
            # process complete
            strategy_trader.set_processing(False)


def alpha_async_update_strategy(strategy, strategy_trader, timestamp: float):
    """
    Override this method to compute a strategy step per instrument.
    Default implementation supports bootstrapping.
    @param strategy:
    @param strategy_trader StrategyTrader Instance of the strategy trader to process.
    @param timestamp: last traded tick or candle timestamp (can be slightly different from strategy timestamp)
    @note Thread-safe method.
    """
    if strategy_trader:
        if strategy_trader.initialized == strategy_trader.STATE_WAITING:
            initiate_strategy_trader(strategy, strategy_trader)

        if strategy_trader.checked == strategy_trader.STATE_WAITING:
            # need to check existing trade orders, trade history and positions
            strategy_trader.check_trades(strategy.timestamp)

        if (strategy_trader.initialized != strategy_trader.STATE_NORMAL or
                strategy_trader.checked != strategy_trader.STATE_NORMAL or
                not strategy_trader.ready()):
            # process only if strategy received any data
            return

        if strategy_trader.processing:
            # process only if previous job was completed
            return

        try:
            strategy_trader.set_processing(True)

            if strategy_trader.bootstrapping == strategy_trader.STATE_WAITING:
                # first : bootstrap using preloaded data history
                alpha_bootstrap(strategy, strategy_trader)
            else:
                # then : until process instrument update
                strategy_trader.process(timestamp)

        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())
        finally:
            # process complete
            strategy_trader.set_processing(False)


def initiate_strategy_trader(strategy, strategy_trader):
    """
    Do it async into the workers to avoid long blocking of the strategy thread.
    """
    if not strategy or not strategy_trader:
        return

    with strategy_trader.mutex:
        if strategy_trader.initialized != strategy_trader.STATE_WAITING:
            # only if waiting for initialize
            return

        if not strategy_trader.instrument:
            return

        strategy_trader.set_initialized(strategy_trader.STATE_PROGRESSING)

    now = datetime.now()

    try:
        # retrieve the related price and volume watcher
        watcher = strategy_trader.instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
        if watcher:
            timeframes = {}

            # subscribes for market data and prefetch recent history
            for analyser in strategy_trader.analysers():
                if not analyser:
                    continue

                if analyser.timeframe > 0.0:
                    timeframes[analyser.timeframe] = analyser.history

            watcher.subscribe(strategy_trader.instrument.market_id, timeframes, None, None)

        # wait to DB commit @todo a method to look if insert are fully flushed before.
        time.sleep(1.0)

        # query for most recent candles per timeframe from the database
        for analyser in strategy_trader.analysers():
            if not analyser:
                continue

            if analyser.timeframe > 0:
                analyser.query_historical_data(to_date=None)

        # initialization processed, waiting for data be ready
        with strategy_trader.mutex:
            strategy_trader.set_initialized(strategy_trader.STATE_NORMAL)

        # wake-up
        strategy.send_update_strategy_trader(strategy_trader.instrument.market_id)

    except Exception as e:
        logger.error(repr(e))
        logger.debug(traceback.format_exc())


#
# backtesting setup
#


# deprecated
def adjust_date_and_last_n(instrument, timeframe, from_date, to_date):
    # crypto are h24, d7, nothing to do
    if instrument.market_type == instrument.TYPE_CRYPTO:
        return from_date, to_date, None

    # there is multiples case, weekend off and nationals days off
    # and the case of stocks markets closed during the local night
    # but also some 15 min of twice on indices ...

    # so many complexes cases then we try to get the max of last n OHLCs
    # here simple direct solution but not correct in case of leaks of data
    depth = max(timeframe['history'], timeframe['depth'])
    n_last = depth

    return None, to_date, n_last


def alpha_setup_backtest(strategy, from_date: datetime, to_date: datetime, base_timeframe=Instrument.TF_TICK):
    """
    Simple load history of OHLCs, initialize all strategy traders here (sync).
    """
    with strategy.mutex:
        strategy_traders = strategy.strategy_traders.values()

    # query for history and initialize feeders
    for strategy_trader in strategy_traders:
        if not strategy_trader.instrument:
            continue

        # retrieve the related price and volume watcher
        watcher = strategy_trader.instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
        if not watcher:
            continue

        # subscribes for market data and query history
        for analyser in strategy_trader.analysers():
            if not analyser:
                continue

            analyser.query_historical_data(from_date)

            # fetch market info from the DB
            Database.inst().load_market_info(strategy.service, watcher.name, strategy_trader.instrument.market_id)

        # create a feeder per instrument for ticks history
        feeder = StrategyDataFeeder(strategy, strategy_trader.instrument.market_id, [], True)
        strategy.add_feeder(feeder)

        feeder.initialize(watcher.name, from_date, to_date)

    # complete initialization state
    for strategy_trader in strategy_traders:
        with strategy_trader.mutex:
            strategy_trader.set_initialized(strategy_trader.STATE_NORMAL)


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

    with strategy.mutex:
        strategy_traders = strategy.strategy_traders.values()

    # query for history and initialize feeders
    for strategy_trader in strategy_traders:
        if strategy_trader.instrument:
            # wake-up all for initialization
            strategy.send_initialize_strategy_trader(strategy_trader.instrument.market_id)

    if strategy.service.load_on_startup:
        strategy.load()

    logger.info("Strategy %s data retrieved" % strategy.name)
