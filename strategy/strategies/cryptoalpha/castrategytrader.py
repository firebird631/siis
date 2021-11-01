# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy trader.

from terminal.terminal import Terminal
from trader.order import Order

from strategy.timeframebasedstrategytrader import TimeframeBasedStrategyTrader
from strategy.strategyassettrade import StrategyAssetTrade

from instrument.instrument import Instrument

from strategy.indicator import utils

from .casuba import CryptoAlphaStrategySubA
from .casubb import CryptoAlphaStrategySubB
from .casubc import CryptoAlphaStrategySubC

import logging
logger = logging.getLogger('siis.strategy.cryptoalpha')


class CryptoAlphaStrategyTrader(TimeframeBasedStrategyTrader):
    """
    Crypto Alpha strategy trader per instrument.
    The defined timeframe must form a chained list of multiple of the previous timeframe. One is the root,
    and the last is the leaf. Each timeframe is unique and is defined by its preceding timeframe.

    - Work with limit order
    - Stop are at market
    - Need at least 15 day of 4h history to have valuables signals (EMA 55)

    @todo Need to cancel a trade if not executed after a specific timeout. If partially executed, after the
    timeout only cancel the buy order, keep the trade active of course.
    """

    def __init__(self, strategy, instrument, params):
        super().__init__(strategy, instrument, Instrument.TF_TICK)

        # mean when there is already a position on the same direction does not increase in the
        # same direction if 0 or increase at max N times
        self.max_trades = params['max-trades']
        self.trade_delay = params['trade-delay']

        self.min_price = params['min-price']
        self.min_vol24h = params['min-vol24h']

        self.min_traded_timeframe = self.timeframe_from_param(params.get('min-traded-timeframe', "15m"))
        self.max_traded_timeframe = self.timeframe_from_param(params.get('max-traded-timeframe', "4h"))

        self.region_allow = params['region-allow']

        self.sltp_timeframe = self.timeframe_from_param(params.setdefault('sltp-timeframe', '1h'))
        self.ref_timeframe = self.timeframe_from_param(params.setdefault('ref-timeframe', '1d'))

        for k, timeframe in self.timeframes_parameters.items():
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

    def filter_market(self, timestamp):
        """
        The first boolean mean accept, the second compute.
        Return True, True if the market is accepted and can be computed this time.
        """
        if timestamp - self._last_filter_cache[0] < 60*60:  # only once per hour
            return self._last_filter_cache[1], self._last_filter_cache[2]

        if not self.instrument.has_spot:
            # only allow buy/sell markets
            self._last_filter_cache = (timestamp, False, False)
            return False, False

        if self.instrument.market_price is not None and self.instrument.market_price < self.min_price:
            # accepted but price is very small (too binary but maybe interesting)
            self._last_filter_cache = (timestamp, True, False)
            return True, False

        if self.instrument.vol24h_quote is not None and self.instrument.vol24h_quote < self.min_vol24h:
            # accepted but 24h volume is very small (rare possibilities of exit)
            self._last_filter_cache = (timestamp, True, False)
            return True, False

        self._last_filter_cache = (timestamp, True, True)
        return True, True

    def process(self, timestamp):
        # update data at tick level
        self.gen_candles_from_ticks(timestamp)

        accept, compute = self.filter_market(timestamp)
        if not accept:
            return

        # and compute
        entries = []
        exits = []

        if compute:
            # we might receive only LONG signals
            entries, exits = self.compute(timestamp)

        #
        # global indicators
        #

        ref_price = self.timeframes[self.ref_timeframe].price.last
        # sma200 = self.timeframes[self.ref_timeframe].sma200.last
        ref_sma55 = self.timeframes[self.ref_timeframe].sma55.last
        ref_sma = self.timeframes[self.ref_timeframe].sma.last
        ref_ema = self.timeframes[self.ref_timeframe].ema.last

        #
        # filters the entries
        #

        retained_entries = []

        # filters entry signal, according to some correlation, parent timeframe signal or trend or trade regions
        for entry in entries:          
            # only allowed range of signal for entry
            if not (self.min_traded_timeframe <= entry.timeframe <= self.max_traded_timeframe):
                continue

            # trade region
            if not self.check_regions(timestamp, self.instrument.market_bid, self.instrument.market_ask,
                                      entry, self.region_allow):
                continue

            # ref timeframe is bear don't take the risk (always long entry)
            if not self.timeframes[self.sltp_timeframe].can_long:
                continue

            atr_stop = self.timeframes[self.sltp_timeframe].atr.stop_loss(entry.dir)
            if atr_stop < self.instrument.open_exec_price(entry.dir):
                entry.sl = atr_stop

            # and a target
            take_profit = self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[2]
            min_take_profit = self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[0]

            # minimal R:R
            gain = (take_profit - entry.p) / entry.p
            loss = (entry.p - entry.sl) / entry.p

            if loss != 0 and (gain / loss < 0.85):  # 0.75 1.0
                Terminal.inst().message("Risk:reward too weak p=%s sl=%s tp=%s rr=%s" % (
                    entry.p, entry.sl, take_profit, (gain/loss)), view="debug")
                continue

            # not enough potential profit (minimal %)
            if gain < 0.01:
                continue

            entry.tp = take_profit
            entry.set('partial-take-profit', 1.0)

            # max loss in %
            if loss < 0.035:
                entry.sl = entry.price * (1-0.035)

                # or not do the trade, to risky
                # continue

            retained_entries.append(entry)

            # # TP 50% entry
            # entry_50pc = StrategySignal(0, 0)
            # entry_50pc.dup(entry)
            # entry_50pc.tp = self.timeframes[self.sltp_timeframe].pivotpoint.last_resistances[0]
            # entry_50pc.set('partial-take-profit', 0.25)

            # retained_entries.append(entry_50pc)

        #
        # process exits signals
        #

        if self.trades:
            with self._trade_mutex:
                for trade in self.trades:
                    retained_exit = None

                    # important if we don't want to update user controlled trades if it have some operations
                    user_mgmt = trade.is_user_trade() and trade.has_operations()

                    # never manage a trade in error state
                    if trade.is_error():
                        continue

                    # important, do not update user controlled trades if it have some operations
                    if trade.is_user_trade() and trade.has_operations():
                        continue

                    for signal in exits:
                        # @todo how to managed exit region ?

                        # receive an exit signal of the timeframe of the trade
                        if signal.timeframe == trade.timeframe:
                            retained_exit = signal
                            break

                        # exit signal on reference timeframe
                        if signal.timeframe == self.ref_timeframe:
                            retained_exit = signal
                            break

                        # exit from any parent timeframe signal
                        # if signal.timeframe > trade.timeframe:
                        #     retained_exit = signal
                        #     break

                    # can cancel a non filled trade if exit signal occurs before timeout (timeframe)
                    # if trade.is_entry_timeout(timestamp, trade.timeframe):
                    #     trader = self.strategy.trader()
                    #     trade.cancel_open(trader, self.instrument)
                    #     Terminal.inst().info("Canceled order (exit signal or entry timeout) %s" % (
                    #         self.instrument.market_id,), view='default')
                    #     continue

                    if user_mgmt:
                        retained_exit = None

                    if trade.is_opened() and not trade.is_valid(timestamp, trade.timeframe):
                        # @todo re-adjust entry
                        Terminal.inst().info("Update order %s trade %s TODO" % (trade.id, self.instrument.market_id,),
                                             view='default')
                        continue

                    # only for active and currently not closing trades
                    if not trade.is_active() or trade.is_closing() or trade.is_closed():
                        continue

                    close_exec_price = self.instrument.close_exec_price(trade.dir)

                    #
                    # stop-loss update
                    #

                    # always need a target, even if user trade and a stop order
                    update_tp = not trade.tp or not trade.has_limit_order()  
                    update_sl = not trade.sl or not trade.has_stop_order()

                    # current sl/tp
                    stop_loss = trade.sl
                    take_profit = trade.tp

                    # ATR stop-loss (always long)
                    atr_stop = self.timeframes[self.sltp_timeframe].atr.stop_loss(trade.direction)
                    if atr_stop > stop_loss:
                        stop_loss = atr_stop

                    if self.timeframes[self.ref_timeframe].pivotpoint.last_pivot > 0.0:
                        if close_exec_price > self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[2]:
                            if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                               self.timeframes[self.ref_timeframe].pivotpoint.resistances[2]):
                                update_tp = True

                            if stop_loss < self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[1]:
                                update_sl = True
                                stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[1]

                        elif close_exec_price > self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[1]:
                            if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                               self.timeframes[self.ref_timeframe].pivotpoint.resistances[1]):
                                update_tp = True

                            if stop_loss < self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[0]:
                                update_sl = True
                                stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[0]

                        elif close_exec_price > self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[0]:
                            if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                               self.timeframes[self.ref_timeframe].pivotpoint.resistances[0]):
                                update_tp = True

                            if stop_loss < self.timeframes[self.ref_timeframe].pivotpoint.last_pivot:
                                update_sl = True
                                stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_pivot

                        elif close_exec_price > self.timeframes[self.ref_timeframe].pivotpoint.last_pivot:
                            if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                               self.timeframes[self.ref_timeframe].pivotpoint.pivot):
                                update_tp = True

                            if stop_loss < self.timeframes[self.ref_timeframe].pivotpoint.last_supports[0]:
                                update_sl = True
                                # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_supports[0]

                        elif close_exec_price > self.timeframes[self.ref_timeframe].pivotpoint.last_supports[0]:
                            if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                               self.timeframes[self.ref_timeframe].pivotpoint.supports[0]):
                                update_tp = True

                            if trade.sl < self.timeframes[self.ref_timeframe].pivotpoint.last_supports[1]:
                                update_sl = True
                                # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_supports[1]

                        elif close_exec_price > self.timeframes[self.ref_timeframe].pivotpoint.last_supports[1]:
                            if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                               self.timeframes[self.ref_timeframe].pivotpoint.supports[1]):
                                update_tp = True

                            if trade.sl < self.timeframes[self.ref_timeframe].pivotpoint.last_supports[2]:
                                update_sl = True
                                # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_supports[2]

                        elif close_exec_price > self.timeframes[self.ref_timeframe].pivotpoint.last_supports[2]:
                            if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                               self.timeframes[self.ref_timeframe].pivotpoint.supports[2]):
                                update_tp = True

                            if close_exec_price < self.timeframes[self.ref_timeframe].pivotpoint.last_supports[2]:
                                update_sl = True
                                # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_supports[2]

                        #
                        # target update
                        #

                        take_profit = self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[int(
                            2*trade.get('partial-take-profit', 0))]

                        # enough potential profit (0.5% min target) (always long)
                        # if (take_profit - close_exec_price) / close_exec_price < 0.005 and update_tp:
                        #     update_tp = False

                        # reevaluate the R:R
                        # gain = (take_profit - trade.entry_price) / trade.entry_price
                        # loss = (trade.entry_price - trade.sl) / trade.entry_price

                        # if loss != 0 and (gain / loss < 0.5):  # 0.75
                        #     # Terminal.inst().message("%s %s %s %s" % (trade.entry_price, trade.sl, take_profit, (gain/loss)), view="debug")
                        #     # @todo force exit
                        #     continue

                    # @todo utiliser OCO, et sinon on peu aussi prioriser un ordre SL si le trade est en perte,
                    #  et plutot un limit si en profit
                    if update_sl and stop_loss > 0:
                        stop_loss = self.instrument.adjust_price(stop_loss)

                        if trade.sl != stop_loss:
                            # logger.info("SL %s %s %s" % (update_sl, stop_loss, trade.sl))

                            delta_time = timestamp - trade.last_stop_loss[0]
                            num_orders = trade.last_stop_loss[1]

                            # too many stop-loss modifications in the timeframe
                            if 0:  # not trade.has_stop_order() or delta_time > 60.0:  # not ((self.sltp_max_rate > num_orders) and (delta_time < self.sltp_max_timeframe)):
                                try:
                                    # OCO order or only bot managed stop-loss, only a TP limit is defined
                                    trade.modify_stop_loss(self.strategy.trader(), self.instrument, stop_loss)
                                except Exception as e:
                                    logger.error(repr(e))

                                Terminal.inst().info("%s modify SL" % timestamp, view="debug")
                            else:
                                trade.sl = stop_loss
                                Terminal.inst().info("%s modify SL" % timestamp, view="debug")

                    if update_tp and take_profit > 0:
                        take_profit = self.instrument.adjust_price(take_profit)

                        if trade.tp != take_profit:
                            # logger.info("TP %s %s %s" % (update_tp, take_profit, trade.tp))

                            delta_time = timestamp - trade.last_take_profit[0]
                            num_orders = trade.last_take_profit[1]

                            # too many stop-loss modifications in the timeframe
                            if not trade.has_limit_order() or delta_time > 60.0:  # not ((self.sltp_max_rate > num_orders) and (delta_time < self.sltp_max_timeframe)):
                                try:
                                    trade.modify_take_profit(self.strategy.trader(), self.instrument, take_profit)
                                except Exception as e:
                                    logger.error(repr(e))

                                # @todo
                                Terminal.inst().info("%s modify TP" % timestamp, view="debug")
                            else:
                                trade.tp = take_profit

                    #
                    # exit trade if an exit signal retained
                    #

                    if retained_exit:
                        self.process_exit(timestamp, trade, retained_exit.price)

        # update actives trades
        self.update_trades(timestamp)

        # retained long entry do the order entry signal
        for entry in retained_entries:
            if not self.process_entry(timestamp, entry.price, entry.tp, entry.sl, entry.timeframe,
                                      entry.get('partial-take-profit', 0)):
                # notify a signal only
                self.notify_signal(timestamp, entry)

        # streaming
        self.stream()

    def process_entry(self, timestamp, price, take_profit, stop_loss, timeframe, partial_tp):
        trader = self.strategy.trader()

        quantity = 0.0
        direction = Order.LONG   # entry is always a long

        # large limit price because else miss the pumping markets
        price = price + self.instrument.market_spread * (1 if trader.paper_mode else 5)  # signal price + spread

        # date_time = datetime.fromtimestamp(timestamp)
        # date_str = date_time.strftime('%Y-%m-%d %H:%M:%S')

        # ajust max quantity according to free asset of quote, and convert in asset base quantity
        if trader.has_asset(self.instrument.quote):
            # quantity = min(quantity, trader.asset(self.instrument.quote).free) / self.instrument.market_ask
            if trader.has_quantity(self.instrument.quote, self.instrument.trade_quantity):
                quantity = self.instrument.adjust_quantity(self.instrument.trade_quantity / price)  # and adjusted to 0/max/step
            else:
                Terminal.inst().notice("Not enought free quote asset %s, has %s but need %s" % (
                    self.instrument.quote,
                    self.instrument.format_quantity(trader.asset(self.instrument.quote).free),
                    self.instrument.format_quantity(self.instrument.trade_quantity)), view='status')

        #
        # create an order
        #

        # only if active
        do_order = self.activity

        order_quantity = 0.0
        order_price = None
        order_type = None
        order_leverage = 1.0

        # simply set the computed quantity
        order_quantity = quantity

        # prefered in limit order at the current best price, and with binance in market
        # INSUFISCENT BALANCE can occurs with market orders...
        order_type = Order.ORDER_LIMIT

        # limit price
        order_price = float(self.instrument.format_price(price))
        # order_price = self.instrument.adjust_price(price)

        #
        # cancellation of the signal
        #

        if order_quantity <= 0 or order_quantity * price < self.instrument.min_notional:
            # min notional not reached
            do_order = False

        if self.trades:
            with self._mutex:
                if len(self.trades) >= self.max_trades:
                    # no more than max simultaneous trades
                    do_order = False

                # for trade in self.trades:
                #     if trade.timeframe == timeframe:
                #         do_order = False

                # if self.trades and (self.trades[-1].dir == direction) and ((timestamp - self.trades[-1].entry_open_time) < self.trade_delay):
                #if self.trades and (self.trades[-1].dir == direction) and ((timestamp - self.trades[-1].entry_open_time) < timeframe):
                #    # the same order occurs just after, ignore it
                #    do_order = False

        #
        # execution of the order
        #

        if do_order:
            trade = StrategyAssetTrade(timeframe)

            # the new trade must be in the trades list if the event comes before, and removed after only it failed
            self.add_trade(trade)

            trade.set('partial-take-profit', partial_tp)

            if trade.open(trader, self.instrument, direction, order_type, order_price, order_quantity,
                          take_profit, stop_loss, order_leverage):
                # notify
                self.notify_trade_entry(timestamp, trade)

                return True
            else:
                self.remove_trade(trade)

        return False

    def process_exit(self, timestamp, trade, exit_price):
        if not self.activity:
            return False

        if trade is None:
            return False

        # close at market as taker
        trader = self.strategy.trader()
        trade.close(trader, self.instrument)
        trade.exit_reason = trade.REASON_CLOSE_MARKET

        return True
