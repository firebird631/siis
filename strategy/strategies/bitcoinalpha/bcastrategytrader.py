# @date 2019-01-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Bitcoin Alpha strategy trader.

from terminal.terminal import Terminal
from trader.order import Order

from strategy.timeframebasedstrategytrader import TimeframeBasedStrategyTrader
from strategy.strategyindmargintrade import StrategyIndMarginTrade

from instrument.instrument import Instrument

from strategy.indicator import utils

from .bcasuba import BitcoinAlphaStrategySubA
from .bcasubb import BitcoinAlphaStrategySubB

import logging
logger = logging.getLogger('siis.strategy.bitcoinalpha')


class BitcoinAlphaStrategyTrader(TimeframeBasedStrategyTrader):
    """
    Bitcoin Alpha strategy trader per instrument.
    Based on CryptoAlpha strategy for margin trading (long/short). Does not support asset (buy/sell) markets.
    The defined timeframe must form a chained list of multiple of the previous timeframe. One is the root,
    and the last is the leaf. Each timeframe is unique and is defined by its preceding timeframe.

    - Enter, exit as possible as maker (limit order)
    - Stop are taker (market order)
    """

    def __init__(self, strategy, instrument, params):
        super().__init__(strategy, instrument, Instrument.TF_TICK)

        # mean when there is already a position on the same direction does not increase in the same
        # direction if 0 or increase at max N times
        self.pyramided = params['pyramided']
        self.max_trades = params['max-trades']

        self.min_price = params['min-price']
        self.min_vol24h = params['min-vol24h']

        self.min_traded_timeframe = self.timeframe_from_param(params.get('min-traded-timeframe', '15m'))
        self.max_traded_timeframe = self.timeframe_from_param(params.get('max-traded-timeframe', '4h'))

        self.region_allow = params['region-allow']

        self.sltp_timeframe = self.timeframe_from_param(params.setdefault('sltp-timeframe', '1h'))
        self.ref_timeframe = self.timeframe_from_param(params.setdefault('ref-timeframe', '1d'))

        self.sltp_max_rate = params.get('modify-max-rate', 3.0)
        self.sltp_max_timeframe = self.timeframe_from_param(params.get('modify-max-timeframe', '1m'))

        for k, timeframe in self.timeframes_parameters.items():
            if timeframe['mode'] == 'A':
                sub = BitcoinAlphaStrategySubA(self, timeframe)
                self.timeframes[timeframe['timeframe']] = sub
            elif timeframe['mode'] == 'B':
                sub = BitcoinAlphaStrategySubB(self, timeframe)
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
        
        if not self.instrument.has_margin or not self.instrument.indivisible_position:
            # only allow margin markets with indivisible position
            self._last_filter_cache = (timestamp, False, False)
            return False, False

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
        # compute the entry
        #
        
        retained_entries = []

        for entry in entries:
            # only allowed range of signal for entry
            if not (self.min_traded_timeframe <= entry.timeframe <= self.max_traded_timeframe):
                continue

            # trade region
            if not self.check_regions(timestamp, self.instrument.market_bid, self.instrument.market_ask, entry,
                                      self.region_allow):
                continue

            # ref timeframe is contrary
            if entry.direction > 0 and not self.timeframes[self.sltp_timeframe].can_long:
                continue

            if entry.direction < 0 and not self.timeframes[self.sltp_timeframe].can_short:
                continue

            # initial stop-loss
            atr_stop = self.timeframes[self.sltp_timeframe].atr.stop_loss(entry.dir)

            loss = 0.0
            gain = 0.0
            take_profit = 0.0

            if entry.direction > 0:
                # and an initial target
                take_profit = self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[2]

                if atr_stop < self.instrument.open_exec_price(entry.dir):
                    entry.sl = atr_stop

                gain = (take_profit - entry.p) / entry.p
                loss = (entry.p - entry.sl) / entry.p

            elif entry.direction < 0:
                # and an initial target
                take_profit = self.timeframes[self.ref_timeframe].pivotpoint.last_supports[2]

                if atr_stop > self.instrument.open_exec_price(entry.dir):
                    entry.sl = atr_stop

                gain = (entry.p - take_profit) / entry.p
                loss = (entry.sl - entry.p) / entry.p

            if loss != 0 and (gain / loss < 1.0):
                Terminal.inst().message("%s %s %s %s %s %s" % (entry.p, entry.sl, take_profit,
                                                               gain, loss, (gain/loss)), view="debug")
                continue

            # not enough potential profit
            if gain < 0.005:
                continue

            entry.tp = take_profit if gain > 0.005 else entry.p * 1.01
            entry.set('partial-take-profit', 1.0)

            # max loss at x%
            if loss > 0.035:
                if entry.direction > 0:
                    entry.sl = entry.price * (1-0.035)
                elif entry.direction < 0:
                    entry.sl = entry.price * (1+0.035)

                # or do not do the trade to risky
                # continue

            retained_entries.append(entry)

            # TP 50% entry
            # entry_50pc = StrategySignal(0, 0)
            # entry_50pc.dup(entry)
            # entry_50pc.tp = np.max(self.timeframes[self.sltp_timeframe].pivotpoint.resistances[0])#[-1]
            # entry_50pc.set('partial-take-profit', 0.25)

            # retained_entries.append(entry_50pc)

        #
        # process eventually exits signals
        #

        if self.trades:
            with self._trade_mutex:
                for trade in self.trades:
                    retained_exit = None

                    # important if we don't want to update user controlled trades if it have some operations
                    user_mgmt = trade.is_user_trade()

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

                    # if trade.is_opened() and not trade.is_valid(timestamp, trade.timeframe):
                    #     # @todo re-adjust entry
                    #     Terminal.inst().info("Update order %s trade %s TODO" % (trade.id,
                    #         self.instrument.market_id,), view='default')
                    #     continue

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

                    # ATR stop-loss (long/short)
                    atr_stop = self.timeframes[self.sltp_timeframe].atr.stop_loss(trade.direction)
                    if trade.direction > 0:
                        # long, greater or initial
                        if atr_stop > stop_loss and atr_stop < close_exec_price * 0.995:
                            stop_loss = atr_stop

                    elif trade.direction < 0:
                        # short, lesser or initial
                        if (atr_stop < stop_loss or stop_loss <= 0) and atr_stop > close_exec_price * 1.005:
                            stop_loss = atr_stop

                    # update take-profit if necessary, and trailing stop-loss
                    if self.timeframes[self.ref_timeframe].pivotpoint.last_pivot > 0.0:
                        if trade.direction > 0:
                            # long
                            if close_exec_price > self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[2]:
                                if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                                   self.timeframes[self.ref_timeframe].pivotpoint.resistances[2]):
                                    update_tp = True

                                if stop_loss < self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[1]:
                                    update_sl = True
                                    # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[1]

                            elif close_exec_price > self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[1]:
                                if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                                   self.timeframes[self.ref_timeframe].pivotpoint.resistances[1]):
                                    update_tp = True

                                if stop_loss < self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[0]:
                                    update_sl = True
                                    # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[0]

                            elif close_exec_price > self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[0]:
                                if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                                   self.timeframes[self.ref_timeframe].pivotpoint.resistances[0]):
                                    update_tp = True

                                if stop_loss < self.timeframes[self.ref_timeframe].pivotpoint.last_pivot:
                                    update_sl = True
                                    # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_pivot

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

                        elif trade.direction < 0:
                            # short (could use the sign, but if we want a non symmetrical approch...)
                            if close_exec_price < self.timeframes[self.ref_timeframe].pivotpoint.last_supports[2]:
                                if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                                   self.timeframes[self.ref_timeframe].pivotpoint.supports[2]):
                                    update_tp = True

                                if close_exec_price > self.timeframes[self.ref_timeframe].pivotpoint.last_supports[2]:
                                    update_sl = True
                                    # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_supports[2]

                            elif close_exec_price < self.timeframes[self.ref_timeframe].pivotpoint.last_supports[1]:
                                if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                                   self.timeframes[self.ref_timeframe].pivotpoint.supports[1]):
                                    update_tp = True

                                if trade.sl > self.timeframes[self.ref_timeframe].pivotpoint.last_supports[2]:
                                    update_sl = True
                                    # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_supports[2]

                            elif close_exec_price < self.timeframes[self.ref_timeframe].pivotpoint.last_supports[0]:
                                if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                                   self.timeframes[self.ref_timeframe].pivotpoint.supports[0]):
                                    update_tp = True

                                if trade.sl > self.timeframes[self.ref_timeframe].pivotpoint.last_supports[1]:
                                    update_sl = True
                                    # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_supports[1]

                            elif close_exec_price < self.timeframes[self.ref_timeframe].pivotpoint.last_pivot:
                                if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                                   self.timeframes[self.ref_timeframe].pivotpoint.pivot):
                                    update_tp = True

                                if stop_loss > self.timeframes[self.ref_timeframe].pivotpoint.last_supports[0]:
                                    update_sl = True
                                    # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_supports[0]

                            elif close_exec_price < self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[0]:
                                if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                                   self.timeframes[self.ref_timeframe].pivotpoint.resistances[0]):
                                    update_tp = True

                                if stop_loss > self.timeframes[self.ref_timeframe].pivotpoint.last_pivot:
                                    update_sl = True
                                    # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_pivot

                            elif close_exec_price < self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[1]:
                                if utils.crossover(self.timeframes[self.ref_timeframe].price.prices,
                                                   self.timeframes[self.ref_timeframe].pivotpoint.resistances[1]):

                                    update_tp = True
                                if stop_loss > self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[0]:
                                    update_sl = True
                                    # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[0]

                            elif close_exec_price < self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[2]:
                                if utils.crossunder(self.timeframes[self.ref_timeframe].price.prices,
                                                    self.timeframes[self.ref_timeframe].pivotpoint.resistances[2]):
                                    update_tp = True

                                if stop_loss > self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[1]:
                                    update_sl = True
                                    # stop_loss = self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[1]

                        #
                        # target update
                        #

                        # enough potential profit (0.5% min target)
                        if trade.direction > 0:
                            take_profit = self.timeframes[self.ref_timeframe].pivotpoint.last_resistances[int(
                                2*trade.get('partial-take-profit', 0))]

                            # if take_profit <= trade.entry_price:
                            #     take_profit = trade.entry_price * 1.05

                            gain = (take_profit - trade.entry_price) / trade.entry_price
                            loss = (trade.entry_price - trade.sl) / trade.entry_price

                        elif trade.direction < 0:
                            take_profit = self.timeframes[self.ref_timeframe].pivotpoint.last_supports[int(
                                2*trade.get('partial-take-profit', 0))]

                            # if take_profit >= trade.entry_price:
                            #     take_profit = trade.entry_price * 0.95

                            gain = (trade.entry_price - take_profit) / trade.entry_price
                            loss = (trade.sl - trade.entry_price) / trade.entry_price

                    # reevaluate the R:R
                    # @todo

                    # if gain < 0.005 and update_tp:
                    #    ...

                    if update_sl and stop_loss > 0:
                        stop_loss = self.instrument.adjust_price(stop_loss)

                        if trade.sl != stop_loss:
                            # logger.info("SL %s %s %s" % (update_sl, stop_loss, trade.sl))

                            delta_time = timestamp - trade.last_stop_loss[0]
                            num_orders = trade.last_stop_loss[1]

                            # too many stop-loss modifications in the timeframe
                            if not trade.has_stop_order() or delta_time > 60.0:  # not ((self.sltp_max_rate > num_orders) and (delta_time < self.sltp_max_timeframe)):
                                try:
                                    trade.modify_stop_loss(self.strategy.trader(), self.instrument, stop_loss)
                                except Exception as e:
                                    logger.error(repr(e))

                                Terminal.inst().info("%s modify SL" % timestamp, view="debug")
                            else:
                                trade.sl = stop_loss

                    if update_tp and take_profit > 0:
                        take_profit = self.instrument.adjust_price(take_profit)

                        if trade.tp != take_profit:
                            logger.info("TP %s %s %s" % (update_tp, take_profit, trade.tp))

                            delta_time = timestamp - trade.last_take_profit[0]
                            num_orders = trade.last_take_profit[1]

                            # too many stop-loss modifications in the timeframe
                            if not trade.has_limit_order() or delta_time > 60.0:  # not ((self.sltp_max_rate > num_orders) and (delta_time < self.sltp_max_timeframe)):
                                try:
                                    trade.modify_take_profit(self.strategy.trader(), self.instrument, take_profit)
                                except Exception as e:
                                    logger.error(repr(e))

                                Terminal.inst().info("%s modify TP" % timestamp, view="debug")
                            else:
                                trade.tp = take_profit

                    #
                    # exit trade if an exit signal retained
                    #

                    if retained_exit:
                        self.process_exit(timestamp, trade, retained_exit.price)
                        Terminal.inst().info("Exit trade %s %s" % (self.instrument.symbol, trade.id), view='debug')

        # update actives trades
        self.update_trades(timestamp)

        # retained long entry do the order entry signal
        for signal in retained_entries:
            if not self.process_entry(timestamp, signal.dir, signal.price, signal.tp, signal.sl, signal.timeframe,
                                      signal.get('partial-take-profit', 0)):
                # notify a signal only
                self.notify_signal(timestamp, signal)

        # streaming
        self.stream()

    def process_entry(self, timestamp, direction, price, take_profit, stop_loss, timeframe, partial_tp):
        if not self.activity:
            return False

        trader = self.strategy.trader()
        quantity = 0.0

        price = self.instrument.open_exec_price(direction)
        quantity = self.compute_margin_quantity(trader, price)

        if quantity <= 0.0:
            return False
    
        #
        # create an order
        #

        order_hedging = False
        order_quantity = 0.0
        order_price = None
        order_type = None
        order_leverage = 1.0

        # simply set the computed quantity
        order_quantity = quantity

        # market or limit
        # order_type = Order.ORDER_MARKET
        order_type = Order.ORDER_LIMIT

        # @todo or trade at order book, compute the limit price from what the order book offer
        # limit best price at tiniest ask price

        # adjust price to min / tick size / max
        order_price = self.instrument.adjust_price(self.instrument.market_ask)

        if take_profit > 0:
            take_profit = self.instrument.adjust_price(take_profit)

        if stop_loss > 0:
            stop_loss = self.instrument.adjust_price(stop_loss)

        #
        # cancellation of the signal
        #

        if not self.check_min_notional(order_quantity, order_price):
            return False

        if self.has_max_trades(self.max_trades):
            return False
 
        #
        # execution of the order
        #

        trade = StrategyIndMarginTrade(timeframe)

        # the new trade must be in the trades list if the event comes before, and removed after only it failed
        self.add_trade(trade)

        trade.set('partial-take-profit', partial_tp)

        if trade.open(trader, self.instrument, direction, order_type, order_price, order_quantity, take_profit,
                      stop_loss, order_leverage, hedging=order_hedging):

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
