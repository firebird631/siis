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
    with strategy_trader._mutex:
        if strategy_trader._bootstrapping != 1:
            # only if waiting for bootstrapping
            return

        # bootstrapping in progress, suspend live until complete
        strategy_trader._bootstrapping = 2

    try:
        if strategy_trader.is_timeframes_based:
            timeframe_based_bootstrap(strategy, strategy_trader)
        elif strategy_trader.is_tickbars_based:
            tickbar_based_bootstrap(strategy, strategy_trader)
    except Exception as e:
        error_logger.error(repr(e))
        traceback_logger.error(traceback.format_exc())

    with strategy_trader._mutex:
        # bootstrapping done, can now branch to live
        strategy_trader._bootstrapping = 0


def timeframe_based_bootstrap(strategy, strategy_trader):
    # captures all initials candles
    initial_candles = {}

    # compute the beginning timestamp
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
        if strategy_trader._initialized == 1:
            initiate_strategy_trader(strategy, strategy_trader)

        if strategy_trader._checked == 1:
            # need to check existing trade orders, trade history and positions
            strategy_trader.check_trades(strategy.timestamp)

        if strategy_trader._initialized != 0 or strategy_trader._checked != 0 or not strategy_trader.instrument.ready():
            # process only if instrument has data
            return

        if strategy_trader._processing:
            # process only if previous job was completed
            return

        try:
            strategy_trader._processing = True

            if strategy_trader._bootstrapping == 1:
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
            strategy_trader._processing = False


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
        if strategy_trader._initialized == 1:
            initiate_strategy_trader(strategy, strategy_trader)

        if strategy_trader._checked == 1:
            # need to check existing trade orders, trade history and positions
            strategy_trader.check_trades(strategy.timestamp)

        if strategy_trader._initialized != 0 or strategy_trader._checked != 0 or not strategy_trader.instrument.ready():
            # process only if instrument has data
            return

        if strategy_trader._processing:
            # process only if previous job was completed
            return

        try:
            strategy_trader._processing = True

            if strategy_trader._bootstrapping == 1:
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
            strategy_trader._processing = False


def initiate_strategy_trader(strategy, strategy_trader):
    """
    Do it async into the workers to avoid long blocking of the strategy thread.
    """
    with strategy_trader._mutex:
        if strategy_trader._initialized != 1:
            # only if waiting for initialize
            return

        strategy_trader._initialized = 2

    now = datetime.now()

    instrument = strategy_trader.instrument
    try:
        watcher = instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
        if watcher:
            # watcher subscriptions
            tfs = {tf['timeframe']: tf['history'] for tf in strategy.parameters.get(
                'timeframes', {}).values() if tf['timeframe'] > 0}

            watcher.subscribe(instrument.market_id, tfs, None, None)

            # wait to DB commit
            # @todo a method to look if insert are fully flushed before, do simply a sleep...
            time.sleep(1.0)

            # wait for timeframes before query
            for k, timeframe in strategy.parameters.get('timeframes', {}).items():
                if timeframe['timeframe'] > 0:
                    instrument.need_timeframe(timeframe['timeframe'])

            # wait for tick-bars (non-temporal bars) before query
            # for k, tickbar in strategy.parameters.get('tickbars', {}).items():
            #     if timeframe['tickbars'] > 0:
            #         instrument.want_tickbar(tickbar['tickbars'])

            # wait for volumes-profiles before query
            # for k, volume_profile in strategy.parameters.get('volume-profiles', {}).items():
            #     if volume_profile['volume-profile'] > 0:
            #         instrument.want_volume_profile(volume_profile['volume-profile'])

            # query for most recent candles per timeframe from the database
            for k, timeframe in strategy.parameters.get('timeframes', {}).items():
                if timeframe['timeframe'] > 0:
                    l_from = now - timedelta(seconds=timeframe['history']*timeframe['timeframe'])
                    l_to = None  # now

                    l_from, l_to, n_last = adjust_date_and_last_n(instrument, timeframe, l_from, l_to)

                    watcher.historical_data(instrument.market_id, timeframe['timeframe'],
                                            from_date=l_from, to_date=l_to, n_last=n_last)

            # initialization processed, waiting for data be ready
            with strategy_trader._mutex:
                strategy_trader._initialized = 0

        # wake-up
        strategy.send_update_strategy_trader(instrument.market_id)

    except Exception as e:
        logger.error(repr(e))
        logger.debug(traceback.format_exc())


#
# backtesting setup
#


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


# def adjust_date_and_last_n(instrument, timeframe, from_date, to_date):
#     # crypto are h24, d7, nothing to do
#     if instrument.market_type == instrument.TYPE_CRYPTO:
#         return from_date, to_date, None
#
#     # there is multiples case, weekend off and nationals days off
#     # and the case of stocks markets closed during the local night
#     # but also some 15 min of twice on indices ...
#
#     # so many complexes cases then we try to get the max of last n OHLCs
#     # depth = max(timeframe['history'], timeframe['depth'])
#     n_last = None
#
#     # but this does not count the regionals holidays
#     day_generator = (from_date + timedelta(x + 1) for x in range((to_date - from_date).days))
#     days_off = sum(1 for day in [from_date] + list(day_generator) if day.weekday() >= 5)
#
#     from_date -= timedelta(days=days_off)
#
#     if instrument.contract_type == instrument.CONTRACT_SPOT or instrument.market_type == instrument.TYPE_STOCK:
#         days_on = sum(1 for day in [from_date] + list(day_generator) if day.weekday() < 5)
#         from_date -= timedelta(seconds=days_on * (24-8)*60*60)
#
#     # need to add night for stock markets
#     if instrument.contract_type == instrument.CONTRACT_SPOT or instrument.market_type == instrument.TYPE_STOCK:
#         pass  # @todo above night data
#
#     return from_date, to_date, n_last


def alpha_setup_backtest(strategy, from_date, to_date, base_timeframe=Instrument.TF_TICK):
    """
    Simple load history of OHLCs, initialize all strategy traders here (sync).
    """
    for market_id, instrument in strategy._instruments.items():
        # retrieve the related price and volume watcher
        watcher = instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
        if watcher:
            # wait for timeframes (temporal bars) before query
            for k, timeframe in strategy.parameters.get('timeframes', {}).items():
                if timeframe['timeframe'] > 0:
                    instrument.need_timeframe(timeframe['timeframe'])

            # wait for tick-bars before query
            # for k, element in strategy.parameters.get('tickbars', {}).items():
            #     if element['tickbar'] > 0:
            #         instrument.need_range_bar(element['tickbar'])

            # wait for volumes-profiles before query
            # for k, volume_profile in strategy.parameters.get('volume-profiles', {}).items():
            #     if volume_profile['volume-profile'] > 0:
            #         instrument.want_volume_profile(volume_profile['volume-profile'])

            # query for most recent OHLC per timeframe from the database
            for k, timeframe in strategy.parameters.get('timeframes', {}).items():
                if timeframe['timeframe'] > 0:
                    l_from = from_date - timedelta(seconds=timeframe['history']*timeframe['timeframe']+1.0)
                    l_to = from_date - timedelta(seconds=1)

                    l_from, l_to, n_last = adjust_date_and_last_n(instrument, timeframe, l_from, l_to)

                    watcher.historical_data(instrument.market_id, timeframe['timeframe'],
                                            from_date=l_from, to_date=l_to, n_last=n_last)

            # query for most recent range-bars from the database
            # for k, element in strategy.parameters.get('tickbars', {}).items():
            #     pass  # @todo it does not comes from watcher but from DB

            # query for most recent candles per timeframe from the database @todo
            # for k, volume_profile in strategy.parameters.get('volume-profiles', {}).items():
            #     pass  # @todo it does not comes from watcher but from DB

            # create a feeder per instrument for ticks history
            feeder = StrategyDataFeeder(strategy, instrument.market_id, [], True)
            strategy.add_feeder(feeder)

            # fetch market info from the DB
            Database.inst().load_market_info(strategy.service, watcher.name, instrument.market_id)

            feeder.initialize(watcher.name, from_date, to_date)

    # initialized state
    for k, strategy_trader in strategy._strategy_traders.items():
        with strategy_trader._mutex:
            strategy_trader._initialized = 0


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

    for market_id, instrument in strategy._instruments.items():
        # wake-up all for initialization
        strategy.send_initialize_strategy_trader(market_id)

    if strategy.service.load_on_startup:
        strategy.load()

    logger.info("Strategy %s data retrieved" % strategy.name)
