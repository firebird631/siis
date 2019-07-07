# @date 2019-01-19
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Bitcoin Alpha strategy trader.

from datetime import datetime
from terminal.terminal import Terminal
from trader.order import Order

from strategy.timeframebasedstrategytrader import TimeframeBasedStrategyTrader
from strategy.strategyindmargintrade import StrategyIndMarginTrade
from strategy.strategysignal import StrategySignal

from instrument.instrument import Instrument

from strategy.indicator import utils

from common.utils import timeframe_to_str

from .bcasuba import BitcoinAlphaStrategySubA
from .bcasubb import BitcoinAlphaStrategySubB
from .bcaparameters import DEFAULT_PARAMS

import logging
logger = logging.getLogger('siis.strategy.bitcoinalpha')


class BitcoinAlphaStrategyTrader(TimeframeBasedStrategyTrader):
    """
    Bitcoin Alpha strategy trader per instrument.
    Based on CryptoAlpha strategy for margin trading (long/short). Does not support asset (buy/sell) markets.
    The defined timeframe must form a chained list of multiple of the previous timeframe. One is the root, and the last is the leaf.
    Each timeframe is unique and is defined by its preceding timeframe.

    - Enter, exit as taker (market order)
    - Stop are taker (market order)

    @todo Finish, update like in CA and in FA strategies
    @todo Implement with a LIMIT (maker/taker) and a LIMIT (maker only) versions.
    @todo Need to cancel a trade if not executed after a specific timeout. If partially executed, after the timeout only cancel the
        buy order, keep the trade active of course.    
    """

    def __init__(self, strategy, instrument, params):
        super().__init__(strategy, instrument, params['base-timeframe'], params['need-update'])

        # mean when there is already a position on the same direction does not increase in the same direction if 0 or increase at max N times
        self.pyramided = params['pyramided']
        self.max_trades = params['max-trades']

        self.min_price = params['min-price']
        self.min_vol24h = params['min-vol24h']

        self.min_traded_timeframe = params['min-traded-timeframe']
        self.max_traded_timeframe = params['max-traded-timeframe']

        for k, timeframe in strategy.timeframes_config.items():
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
        
        trader = self.strategy.trader()

        if not trader:
            self._last_filter_cache = (timestamp, False, False)
            return False, False

        market = trader.market(self.instrument.market_id)

        if not market:
            self._last_filter_cache = (timestamp, False, False)
            return False, False

        if market.trade != market.TRADE_IND_MARGIN and market.trade != market.TRADE_MARGIN:
            # only allow margin markets
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

        #
        # global indicators
        #

        # a voir car les 1m et 5m peuvent aussi se trader mais ça engendre trop de risk en trend bear
        SLOW_TIMEFRAME = Instrument.TF_4HOUR

        price_above_slow_sma55 = 0
        price_above_slow_sma200 = 0
        sma55_above_sma200 = 0
        sma_above_sma55 = 0

        last_price = self.timeframes[Instrument.TF_4HOUR].price.last
        sma = self.timeframes[Instrument.TF_4HOUR].sma.last
        ema = self.timeframes[Instrument.TF_4HOUR].ema.last
        sma55 = self.timeframes[Instrument.TF_4HOUR].sma55.last
        sma200 = self.timeframes[Instrument.TF_4HOUR].sma200.last
        rsi21 = self.timeframes[Instrument.TF_4HOUR].rsi.last

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
            if not entry.sl:
                # ATR stop-loss (long/short)
                sl = self.timeframes[entry.timeframe].atr.stop_loss(entry.direction)
                if entry.direction > 0:
                    if sl < last_price:
                        entry.sl = sl
                elif entry.direction < 0:
                    if sl > last_price:
                        entry.sl = sl

            retained_entries.append(entry)

        #
        # process eventually exits signals
        #

        if self.trades:
            self.lock()

            for trade in self.trades:
                tf_match = False
                retained_exit = None

                # important, do not update user controlled trades if it have some operations
                if trade.is_user_trade() and trade.has_operations():
                    continue

                for signal in exits:
                    #hi_signal_tf = self.parent_timeframe(signal.timeframe)

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

                # if not retained_exit:
                #     for signal in entries:
                #         if signal.timeframe == trade.timeframe and trade.direction != signal.direction:
                #             # opposite entry mean exit signal
                #             retained_exit = signal.as_exit()
                #             break

                #
                # stop loss
                #

                stop_loss = trade.sl

                # ATR stop-loss (long/short)
                atr_stop = self.timeframes[trade.timeframe].atr.stop_loss(trade.direction)
                if trade.direction > 0:
                    if atr_stop > stop_loss:
                        stop_loss = atr_stop
                elif trade.direction < 0:
                    if atr_stop < stop_loss:
                        stop_loss = atr_stop

                # if trade.direction > 0 and trade.get_stats()['best-price'] > 0:
                #     if last_price <= (trade.get_stats()['best-price'] * 0.4 + trade.entry_price * 0.6) and last_price > stop_loss:
                #         stop_loss = last_price
                # elif trade.direction < 0 and trade.get_stats()['best-price'] > 0:
                #     if last_price >= (trade.get_stats()['best-price'] * 0.4 + trade.entry_price * 0.6) and last_price < stop_loss:
                #         stop_loss = last_price

                # bb_ma = self.timeframes[trade.timeframe].bollingerbands.last_ma
                # if trade.direction > 0:
                #     if bb_ma > stop_loss and last_price > bb_ma:
                #         stop_loss = bb_ma
                # elif trade.direction < 0:
                #     if bb_ma < stop_loss and last_price < bb_ma:
                #         stop_loss = bb_ma

                # if trade.direction > 0:
                #     pivotpoint = self.timeframes[trade.timeframe].pivotpoint.last_supports[0]
                #     if pivotpoint > stop_loss:
                #         stop_loss = pivotpoint
                # elif trade.direction < 0:
                #     pivotpoint = self.timeframes[trade.timeframe].pivotpoint.last_resistances[0]
                #     if pivotpoint < stop_loss:
                #         trade.sl = pivotpoint

                # stop_loss = trade.sl
                # level = (atr_stop * 0.2 + pivotpoint * 0.8) # (atr_stop + bb_ma) * 0.5
                # if trade.direction > 0:
                #     if level > stop_loss:
                #         stop_loss = level
                # elif trade.direction < 0:
                #     if level < stop_loss:
                #         stop_loss = level

                if stop_loss != trade.sl:
                    trade.sl = stop_loss

                # @todo could use trade.modify_stop_loss

                # can cancel a non filled trade if exit signal occurs before timeout (timeframe)
                # if (trade.is_opened() and tf_match) or trade.is_entry_timeout(timestamp, trade.timeframe):
                # if trade.is_entry_timeout(timestamp, trade.timeframe):
                #     trader = self.strategy.trader()
                #     trade.cancel_open(trader)
                #     # Terminal.inst().info("Canceled order (exit signal or entry timeout) %s" % (self.instrument.market_id,), view='default')
                #     continue

                if trade.is_opened() and not trade.is_valid(timestamp, trade.timeframe):
                    # @todo re-adjust entry
                    Terminal.inst().info("Update order %s trade %s TODO" % (trade.id, self.instrument.market_id,), view='default')
                    continue

                # only for active and currently not closing trades
                if not trade.is_active() or trade.is_closing() or trade.is_closed():
                    continue

                # ROE (long/short) @todo or optimize ATR, we need volatility index
                # if trade.direction > 0:
                #     if (last_price - trade.entry_price) / trade.entry_price >= 0.0075:
                #         sl = trade.entry_price + (trade.entry_price * 0.001 * 2)
                #         if trade.sl < sl:
                #             trade.sl = sl
                # elif trade.direction < 0:
                #     if (trade.entry_price - last_price) / trade.entry_price >= 0.0075:
                #         sl = trade.entry_price - (trade.entry_price * 0.001 * 2)
                #         if trade.sl > sl:
                #             trade.sl = sl

                # take-profit update
                # @todo

                if retained_exit:
                    # exit the trade
                    self.process_exit(timestamp, trade, retained_exit.price)

            self.unlock()

        # update actives trades
        self.update_trades(timestamp)

        # retained long entry do the order entry signal
        for entry in retained_entries:
            # @todo problem want only in live mode, not during backtesting
            height = 0  # self.instrument.height(entry.timeframe, -1)

            # @todo or trade at order book, compute the limit price from what the order book offer or could use ATR
            signal_price = entry.price + height

            self.process_entry(timestamp, entry.dir, signal_price, entry.tp, entry.sl, entry.timeframe)

        # streaming
        self.stream()

    def count_quantities(self, direction):
        """
        Return the actual quantity of any of the position on this market on the two directions.
        @return tuple (on the same direction, on the opposite direction)
        """
        trader = self.strategy.trader()

        current_opposite_qty = 0.0
        current_same_qty = 0.0

        positions = trader.positions(self.instrument.market_id)

        for position in positions:
            if position.direction != direction:
                # have in opposite directions ? close them !
                current_opposite_qty += position.quantity
            else:
                # or same direction ?
                current_same_qty += position.quantity

        return current_same_qty, current_opposite_qty

    def process_entry(self, timestamp, direction, price, take_profit, stop_loss, timeframe):
        trader = self.strategy.trader()
        market = trader.market(self.instrument.market_id)

        quantity = 0.0
        price = market.ofr # signal is at ofr price (for now limit entry at current ofr price)

        date_time = datetime.fromtimestamp(timestamp)
        date_str = date_time.strftime('%Y-%m-%d %H:%M:%S')

        # ajust max quantity according to free asset of quote, and convert in asset base quantity
        if 0: # not trader.has_margin(self.market.margin_cost(self.instrument.trade_quantity)):
            Terminal.inst().notice("Not enought free margin %s, has %s but need %s" % (
                market.quote, market.format_quantity(trader.account.margin_balance), market.format_quantity(self.instrument.trade_quantity)), view='status')
        else:
            quantity = market.adjust_quantity(self.instrument.trade_quantity)
    
        #
        # create an order
        #

        do_order = self.activity

        order_hedging = False
        order_quantity = 0.0
        order_price = None
        order_type = None
        order_leverage = 1.0

        # simply set the computed quantity
        order_quantity = quantity
        order_type = Order.ORDER_MARKET  #  Order.ORDER_LIMIT @todo limit later

        # @todo or trade at order book, compute the limit price from what the order book offer
        # limit best price at tiniest ofr price

        # adjust price to min / tick size / max
        order_price = market.adjust_price(market.ofr)

        if take_profit > 0:
            take_profit = market.adjust_price(take_profit)

        if stop_loss > 0:
            stop_loss = market.adjust_price(stop_loss)

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
                if trade.timeframe == timeframe or trade.direction != direction:
                    # not on the same timeframe and cannot hedge on crypto market
                    do_order = False

            # if self.trades and (self.trades[-1].dir == direction) and ((timestamp - self.trades[-1].entry_open_time) < self.trade_delay):
            if self.trades and (self.trades[-1].dir == direction) and ((timestamp - self.trades[-1].entry_open_time) < timeframe):
                # the same order occurs just after, ignore it
                do_order = False

            self.unlock()
 
        #
        # execution of the order
        #

        if do_order:
            trade = StrategyIndMarginTrade(timeframe)

            logger.info("Order %s %s qty=%s p=%s sl=%s tp=%s ts=%s" % ("long" if direction > 0 else "short", self.instrument.market_id,
                market.format_quantity(order_quantity), market.format_price(order_price), market.format_price(stop_loss), market.format_price(take_profit), date_str))

            # the new trade must be in the trades list if the event comes before, and removed after only it failed
            self.add_trade(trade)

            if trade.open(trader, self.instrument.market_id, direction, order_type, order_price, order_quantity, take_profit, stop_loss, order_leverage, hedging=order_hedging):
                # initiate the take-profit limit order
                if take_profit > 0:
                    trade.modify_take_profit(trader, self.instrument.market_id, take_profit)

                # # initiate the stop-loss order
                # if stop_loss > 0:
                #     trade.modify_stop_loss(trader, self.instrument.market_id, stop_loss)

                # notify
                self.strategy.notify_order(trade.id, trade.dir, self.instrument.market_id, market.format_price(price),
                        timestamp, trade.timeframe, 'entry', None, market.format_price(trade.sl), market.format_price(trade.tp))

                # want it on the streaming (take care its only the order signal, no the real complete execution)
                if trade.direction > 0:
                    self._global_streamer.member('buy-entry').update(price, timestamp)
                elif trade.direction < 0:
                    self._global_streamer.member('sell-entry').update(price, timestamp)
            else:
                self.remove_trade(trade)

    def process_exit(self, timestamp, trade, exit_price):
        if trade is None:
            return

        do_order = self.activity

        if do_order:
            # close at market as taker
            trader = self.strategy.trader()
            trade.close(trader, self.instrument.market_id)

            if trade.direction > 0:
                self._global_streamer.member('buy-exit').update(exit_price, timestamp)
            elif trade.direction < 0:
                self._global_streamer.member('sell-exit').update(exit_price, timestamp)

            market = trader.market(self.instrument.market_id)

            # estimed profit/loss rate
            if trade.direction > 0:
                profit_loss_rate = (exit_price - trade.entry_price) / trade.entry_price
            elif trade.direction < 0:
                profit_loss_rate = (trade.entry_price - exit_price) / trade.entry_price
            else:
                profit_loss_rate = 0

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
