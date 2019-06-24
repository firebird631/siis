# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy trader.

import time
import datetime
import copy

import numpy as np

from terminal.terminal import Terminal
from trader.order import Order

from strategy.timeframebasedstrategytrader import TimeframeBasedStrategyTrader
from strategy.strategyassettrade import StrategyAssetTrade
from strategy.strategysignal import StrategySignal

from instrument.instrument import Instrument

from strategy.indicator import utils

from common.utils import timeframe_to_str

from .casuba import CryptoAlphaStrategySubA
from .casubb import CryptoAlphaStrategySubB
from .casubc import CryptoAlphaStrategySubC

import logging
logger = logging.getLogger('siis.strategy.cryptoalpha')


class CryptoAlphaStrategyTrader(TimeframeBasedStrategyTrader):
    """
    Crypto Alpha strategy trader per instrument.
    The defined timeframe must form a chained list of multiple of the previous timeframe. One is the root, and the last is the leaf.
    Each timeframe is unique and is defined by its preceding timeframe.

    - Work with limit order
    - Stop are at market
    - Need at least 15 day of 4h history to have valuables signals (EMA 55)

    @todo Need to cancel a trade if not executed after a specific timeout. If partially executed, after the timeout only cancel the
        buy order, keep the trade active of course.
    """

    def __init__(self, strategy, instrument, params):
        super().__init__(strategy, instrument, params['base-timeframe'], params['need-update'])

        # mean when there is already a position on the same direction does not increase in the same direction if 0 or increase at max N times
        self.max_trades = params['max-trades']
        self.trade_delay = params['trade-delay']

        self.min_price = params['min-price']
        self.min_vol24h = params['min-vol24h']

        self.min_traded_timeframe = params['min-traded-timeframe']
        self.max_traded_timeframe = params['max-traded-timeframe']

        for timeframe in strategy.timeframes_config:
            if timeframe['mode'] == 'A':
                sub = CryptoAlphaStrategySubA(self, timeframe)
                self.timeframes[timeframe['timeframe']] = sub
            elif timeframe['mode'] == 'B':
                sub = CryptoAlphaStrategySubB(self, timeframe)
                self.timeframes[timeframe['timeframe']] = sub
            elif timeframe['mode'] == 'C':
                sub = CryptoAlphaStrategySubC(self, timeframe)
                self.timeframes[timeframe['timeframe']] = sub
            else:   
                continue

        self._last_filter_cache = (0, False, False)

        self.setup_streaming()

        # @todo remove (debug only) need subscriber
        if list(self.strategy._instruments.values())[0] == self.instrument:
            for tf in (Instrument.TF_15MIN, Instrument.TF_4HOUR):
                if tf not in self._timeframe_streamers:
                    streamer = self.create_chart_streamer(self.timeframes[tf])
                    if streamer:
                        self._timeframe_streamers[tf] = streamer

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

        if market.trade != market.TRADE_BUY_SELL:
            # only allow buy/sell markets
            self._last_filter_cache = (timestamp, False, False)
            return False, False

        # if there is no actives trades we can avoid computation on some ininteresting markets
        if not self.trades:
            if market.price is not None and market.price < self.min_price:
                # accepted but price is very small (too binary but maybe interesting)
                self._last_filter_cache = (timestamp, True, False)
                return True, False

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
            # we might receive only LONG signals
            entries, exits = self.compute(timeframe, timestamp)

        #
        # global indicators
        #

        price_above_slow_sma55 = 0
        price_above_slow_sma200 = 0
        sma55_above_sma200 = 0
        sma_above_sma55 = 0

        REF_TIMEFRAME = Instrument.TF_4HOUR

        last_price = self.timeframes[REF_TIMEFRAME].price.last
        sma = self.timeframes[REF_TIMEFRAME].sma.last
        ema = self.timeframes[REF_TIMEFRAME].ema.last
        sma55 = self.timeframes[REF_TIMEFRAME].sma55.last
        sma200 = self.timeframes[REF_TIMEFRAME].sma200.last
        rsi21 = self.timeframes[REF_TIMEFRAME].rsi.last

        if last_price > sma55:
            price_above_slow_sma55 = 1
        elif last_price < sma55:
            price_above_slow_sma55 = -1

        # if last_price > sma200:
        #     price_above_slow_sma200 = 1
        # elif last_price < sma200:
        #     price_above_slow_sma200 = -1

        #
        # major trend detection
        #

        major_trend = 0

        if (sma and sma55 and last_price and rsi21):
            # not having main trend and at least 1 sample OR not in the trend
            if ema < sma:
                major_trend = -1
                # Terminal.inst().info("Bear major trend SMA ema=%s sma=%s sma55=%s rsi21=%s" % (ema, sma, sma55, rsi21), view="default")
            elif ema > sma:
                major_trend = 1

            # if price_above_slow_sma55 < 0:               
            #     major_trend = -1
            #     # Terminal.inst().message("Bear trend... rsi=%.2f ema=%.2f price=%s" % (rsi21, sma55, last_price), view='default')
            # elif price_above_slow_sma55 > 0:
            #     major_trend = 1

        #
        # compute the entry
        #

        retained_entries = []

        for entry in entries:
            parent_entry_tf = self.parent_timeframe(entry.timeframe)

            # > ENTRY.C1
            # only allowed range of signal for entry
            if not (self.min_traded_timeframe <= entry.timeframe <= self.max_traded_timeframe):
                continue
            # < ENTRY.C1

            # > ENTRY.C5
            # ignore if bear major trend for some timeframes only for BTC quote markets
            # if major_trend < 0 and entry.timeframe >= Instrument.TF_15MIN:
            #     continue
            # < ENTRY.C5

            # > ENTRY.C2 (discutable, redondant)
            # if exits and exits[-1].timeframe > entry.timeframe and major_trend < 0:
            # if exits and exits[-1].timeframe > entry.timeframe:
            #     # good entry but higher timeframe say to exit, don't take the entry
            #     Terminal.inst().message("Reject this entry: exit from higher timeframe ! %s" % str(entry), view='default')
            #     continue
            # < ENTRY.C2

            # > ENTRY.C3
            # signal upper timeframe trend (pas tres pertinant au final)
            # # upper_tf = self.parent_timeframe(entry.timeframe)
            # upper_tf, low, high, trend = self.higher_timeframe_low_high_trend(entry.timeframe)

            # # ignore if parent timeframe not recently confirm the entry
            # if self.timeframes[upper_tf].last_signal:
            #     if not entry.compare(self.timeframes[upper_tf].last_signal):
            #         Terminal.inst().message("Reject this entry: from parent timeframe ! %s" % str(retained_entry), view='default')
            #         continue
            #     else:
            #         Terminal.inst().message("Reject this entry: not parent timeframe confirmation ! %s" % str(entry), view='default')
            #         continue
            # < ENTRY.C3

            # > ENTRY.C4
            # for exit in exits:
            #     if parent_entry_tf == exit.timeframe:
            #         retained_entry = None
            #         Terminal.inst().message("Reject this entry ! %s" % str(retained_entry), view='default')
            #         continue
            # < ENTRY.C4

            # TDST does not give us a stop, ok lets find one
            # if not entry.sl:
            #     # ATR stop-loss
            #     sl = self.timeframes[entry.timeframe].atr.stop_loss(entry.dir)
            #     if sl < last_price:
            #         entry.sl = sl

            retained_entries.append(entry)

        #
        # process eventually exits signals
        #

        if self.trades:
            self.lock()

            for trade in self.trades:
                tf_match = False
                retained_exit = None

                # don't manage user trade here
                if trade.is_user_managed():
                    continue

                for signal in exits:
                    hi_signal_tf = self.parent_timeframe(signal.timeframe)

                    # EX.C1 receive an exit signal for a timeframe defined in an active trade
                    if signal.timeframe == trade.timeframe:
                        retained_exit = signal
                        tf_match = True
                        break

                    # EX.C2 fait sortir trop tot souvent sur YOYOBTC
                    # if hi_signal_tf == trade.timeframe: 
                    #     logger.info("> Exit signal from lower timeframe")
                    #     tf_match = True
                    #     break

                    # EX.C3
                    # if signal.timeframe > trade.timeframe:  # testing
                    #     tf_match = True
                    #     break

                # can cancel a non filled trade if exit signal occurs before timeout (timeframe)
                # if (trade.is_opened() and tf_match) or trade.is_entry_timeout(timestamp, trade.timeframe):
                if trade.is_entry_timeout(timestamp, trade.timeframe):
                    trader = self.strategy.trader()
                    trade.cancel_open(trader)
                    Terminal.inst().info("Canceled order (exit signal or entry timeout) %s" % (self.instrument.market_id,), view='default')
                    continue

                if trade.is_opened() and not trade.is_valid(timestamp, trade.timeframe):
                    # @todo re-adjust entry
                    Terminal.inst().info("Update order %s trade %s TODO" % (trade.id, self.instrument.market_id,), view='default')
                    continue

                # only for active and currently not closing trades
                if not trade.is_active() or trade.is_closing() or trade.is_closed():
                    continue

                stop_loss = trade.sl

                # ATR stop-loss update
                sl = self.timeframes[trade.timeframe].atr.stop_loss(trade.direction)
                if sl > stop_loss:
                    stop_loss = sl

                # # profitable stop-loss for long direction
                # for resistances in self.timeframes[trade.timeframe].pivotpoint.resistances:
                #     if len(resistances):
                #         level = np.min(resistances)
                #         if last_price >= level and level > stop_loss:
                #             stop_loss = level

                # for supports in self.timeframes[trade.timeframe].pivotpoint.supports:
                #     if len(supports):
                #         level = np.max(supports)
                #         if last_price >= level and level > stop_loss:
                #             stop_loss = level

                # need a parameters, or compute using ATR
                # if (trade.get_stats()['best-price'] - trade.p) / trade.p >= 0.0075:
                #     sl = trade.p + (trade.p * 0.001 * 2)
                #     if sl > trade.sl:
                #         stop_loss = sl

                # level = self.timeframes[trade.timeframe].bollingerbands.last_ma
                # if level >= stop_loss:
                #     trade.sl = level
                #     # trade.modify_stop_loss(trader, stop_loss)

                if retained_exit:
                    # exit the trade
                    self.process_exit(timestamp, trade, retained_exit.p)

            self.unlock()

        # update actives trades
        self.update_trades(timestamp)

        # retained long entry do the order entry signal
        for entry in retained_entries:
            # @todo problem want only in live mode, not during backtesting
            height = 0  # self.instrument.height(entry.timeframe, -1)

            # @todo or trade at order book, compute the limit price from what the order book offer or could use ATR
            signal_price = entry.p + height

            self.process_entry(timestamp, signal_price, entry.tp, entry.sl, entry.timeframe)

        # streaming
        self.stream()

    def process_entry(self, timestamp, price, take_profit, stop_loss, timeframe):
        trader = self.strategy.trader()
        market = trader.market(self.instrument.market_id)

        quantity = 0.0
        direction = Order.LONG   # entry is always a long
        price = price + market.spread  # signal price + spread

        # date_time = datetime.datetime.fromtimestamp(timestamp)
        # date_str = date_time.strftime('%Y-%m-%d %H:%M:%S')

        # ajust max quantity according to free asset of quote, and convert in asset base quantity
        if trader.has_asset(market.quote):
            # quantity = min(quantity, trader.asset(market.quote).free) / market.ofr
            if trader.has_quantity(market.quote, self.instrument.trader_quantity):
                quantity = market.adjust_quantity(self.instrument.trader_quantity / price)  # and adjusted to 0/max/step
            else:
                Terminal.inst().notice("Not enought free quote asset %s, has %s but need %s" % (
                    market.quote, market.format_quantity(trader.asset(market.quote).free), market.format_quantity(self.instrument.trader_quantity)), view='status')

        #
        # create an order
        #

        # only if active
        do_order = self.strategy.activity

        order_quantity = 0.0
        order_price = None
        order_type = None
        order_leverage = 1.0

        # simply set the computed quantity
        order_quantity = quantity

        # prefered in limit order at the current best price, and with binance in market INSUFISCENT BALANCE can occurs with market orders...
        order_type = Order.ORDER_LIMIT

        # limit price
        order_price = float(market.format_price(price))
        # order_price = market.adjust_price(price)

        #
        # cancelation of the signal
        #

        if order_quantity <= 0 or order_quantity * price < market.min_notional:
            # min notional not reached
            do_order = False

        if self.trades:
            self.lock()

            if len(self.trades) >= self.max_trades:
                # no more than max simultaneous trades
                do_order = False

            for trade in self.trades:
                if trade.timeframe == timeframe:
                    do_order = False

            # if self.trades and (self.trades[-1].dir == direction) and ((timestamp - self.trades[-1].t) < self.trade_delay):
            if self.trades and (self.trades[-1].dir == direction) and ((timestamp - self.trades[-1].t) < timeframe):
                # the same order occurs just after, ignore it
                do_order = False

            self.unlock()

        #
        # execution of the order
        #

        if do_order:
            trade = StrategyAssetTrade(timeframe)

            # the new trade must be in the trades list if the event comes before, and removed after only it failed
            self.add_trade(trade)

            if trade.open(trader, self.instrument.market_id, direction, order_type, order_price, order_quantity, take_profit, stop_loss, order_leverage):
                # notify
                self.strategy.notify_order(trade.id, trade.dir, self.instrument.market_id, market.format_price(price),
                        timestamp, trade.timeframe, 'entry', None, market.format_price(trade.sl), market.format_price(trade.tp))

                # want it on the streaming (take care its only the order signal, no the real complete execution)
                self._global_streamer.member('buy-entry').update(price, timestamp)
            else:
                self.remove_trade(trade)

        else:
            # notify a signal only
            self.strategy.notify_order(-1, Order.LONG, self.instrument.market_id, market.format_price(price),
                    timestamp, timeframe, 'entry', None, market.format_price(stop_loss), market.format_price(take_profit))

    def process_exit(self, timestamp, trade, exit_price, immediate=True):
        if trade is None:
            return

        do_order = self.strategy.activity

        if do_order:
            if immediate:
                # close at market as taker
                trader = self.strategy.trader()
                trade.close(trader, self.instrument.market_id)

                self._global_streamer.member('buy-exit').update(exit_price, timestamp)

                market = trader.market(self.instrument.market_id)

                # estimed profit/loss rate
                profit_loss_rate = (exit_price - trade.p) / trade.p

                # estimed maker/taker fee rate for entry and exit
                if trade.get_stats()['entry-maker']:
                    profit_loss_rate -= market.maker_fee
                else:
                    profit_loss_rate -= market.taker_fee

                if trade.get_stats()['exit-maker']:
                    profit_loss_rate -= market.maker_fee
                else:
                    profit_loss_rate -= market.taker_fee

                # notify
                self.strategy.notify_order(trade.id, trade.dir, self.instrument.market_id, market.format_price(exit_price),
                        timestamp, trade.timeframe, 'exit', profit_loss_rate)
            else:
                # delayed

                # will exit at market, using update_trade on the next iteration
                trade.sl = exit_price if exit_price < trade.p else 0
                trade.tp = exit_price if exit_price > trade.p else 0

                # or will create an exit order
                # trader = self.strategy.trader()
                # trade.modify_take_profit(trader, self.instrument.market_id, exit_price)
                # trade.modify_stop_loss(trader, self.instrument.market_id, exit_price)
