# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Forex Alpha strategy

from datetime import datetime
from common.utils import UTC

from terminal.terminal import Terminal
from trader.order import Order

from strategy.strategypositiontrade import StrategyPositionTrade
from strategy.strategysignal import StrategySignal
from strategy.timeframebasedstrategytrader import TimeframeBasedStrategyTrader

from instrument.instrument import Instrument

from strategy.indicator import utils
from strategy.indicator.score import Score

from common.utils import timeframe_to_str

from .fasuba import ForexAlphaStrategySubA
from .fasubb import ForexAlphaStrategySubB
from .fasubc import ForexAlphaStrategySubC

from .faparameters import DEFAULT_PARAMS

import logging
logger = logging.getLogger('siis.strategy.forexalpha')


class ForexAlphaStrategyTrader(TimeframeBasedStrategyTrader):
    """
    Forex Alpha strategy trader.
    """

    def __init__(self, strategy, instrument, params):
        super().__init__(strategy, instrument, Instrument.TF_TICK)

        # mean when there is already a position on the same direction does not increase in the same direction if 0 or increase at max N times
        self.pyramided = params['pyramided']
        self.max_trades = params['max-trades']
        self.hedging = params['hedging']  # only if the broker/market allow it

        self.min_traded_timeframe = self.timeframe_from_param(params.get('min-traded-timeframe', "15m"))
        self.max_traded_timeframe = self.timeframe_from_param(params.get('max-traded-timeframe', "4h"))

        # self.score_trigger = params['score-trigger']
        # self.score_increase_factor = params['score-increase-factor']
        # self.score_regression_factor = params['score-regression-factor']

        # self.score_confidence_level = params['score-confidence-level']
        # self.score_default_factor = params['score-default-factor']
        # self.score_div_factor = params['score-div-factor']
        # self.score_cross_factor = params['score-cross-factor']

        # score_trigger = self.score_trigger
        # score_increase_factor = self.score_increase_factor
        # score_regression_factor = self.score_regression_factor

        # self.scorify = Scorify(score_trigger, score_increase_factor, score_regression_factor)

        for k, timeframe in strategy.timeframes_config.items():
            if timeframe['mode'] == 'A':
                sub = ForexAlphaStrategySubA(self, timeframe)
                self.timeframes[timeframe['timeframe']] = sub
            elif timeframe['mode'] == 'B':
                sub = ForexAlphaStrategySubB(self, timeframe)
                self.timeframes[timeframe['timeframe']] = sub
            elif timeframe['mode'] == 'C':
                sub = ForexAlphaStrategySubC(self, timeframe)
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

        if not self.instrument.has_margin:
            # only allow margin markets
            self._last_filter_cache = (timestamp, False, False)
            return False, False

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
            elif ema > sma:
                major_trend = 1

            # if price_above_slow_sma55 < 0:               
            #     major_trend = -1
            # elif price_above_slow_sma55 > 0:
            #     major_trend = 1

        #
        # compute the entry
        #
        
        retained_entries = []
        for entry in entries:
            # > ENTRY.C1
            # only allowed range of signal for entry
            if not (self.min_traded_timeframe <= entry.timeframe <= self.max_traded_timeframe):
                continue
            # < ENTRY.C1

            # filter some period of time
            # 1) no trade between 20:45 and 21:45 (22:45 UTC+1 summer time +1) => no trade before overnight and surrounding
            # 2) no trade between 00:00 and 02:59 (bad spread, no way moves...)
            # 3) no trade between 12:25 and 13:35 (14:25 UTC+1 summer time +1) => always move erratically at US premarket
            # cur_dt = datetime.fromtimestamp(timestamp, tz=UTC())
            # if ((cur_dt.hour >= 20) and (cur_dt.minute >= 45)) and ((cur_dt.hour <= 23) and (cur_dt.minute <= 59)):
            #     continue

            # if ((cur_dt.hour >= 0) and (cur_dt.minute >= 0)) and ((cur_dt.hour <= 2) and (cur_dt.minute <= 59)):
            #     continue

            # if ((cur_dt.hour >= 12) and (cur_dt.minute >= 25)) and ((cur_dt.hour <= 13) and (cur_dt.minute <= 35)):
            #    continue

            # > ENTRY.C5
            # ignore if bear major trend for some timeframes only for BTC quote markets
            # if major_trend < 0 and entry.timeframe >= Instrument.TF_15MIN:
            #     continue
            # < ENTRY.C5

            # > ENTRY.C4
            # for exit in exits:
            #     if parent_entry_tf == exit.timeframe:
            #         retained_entry = None
            #         logger.info("Reject this entry ! %s" % str(retained_entry))
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

        if self.trades:
            with self._trade_mutex:
                for trade in self.trades:
                    tf_match = False
                    retained_exit = None

                    # important, do not update user controlled trades if it have some operations
                    if trade.is_user_trade() and trade.has_operations():
                        continue

                    #
                    # process eventually exits signals
                    #

                    for signal in exits:
                        # EX.C1 receive an exit signal for a timeframe defined in an active trade
                        # @todo probably not the best solution because could have some TD9 but at 
                        # lower timeframe could be not be the best
                        if signal.timeframe == trade.timeframe:
                            retained_exit = signal
                            tf_match = True
                            break

                    if not retained_exit:
                        for signal in entries:
                            if signal.timeframe == trade.timeframe and trade.direction != signal.direction:
                                # opposite entry mean exit signal
                                retained_exit = signal.as_exit()
                                break

                    #
                    # dynamic stop loss
                    #

                    stop_loss = trade.sl

                    # @todo update as bcastrategytrader

                    # ATR stop-loss (long/short)
                    atr_stop = self.timeframes[trade.timeframe].atr.stop_loss(trade.direction)
                    if trade.direction > 0:
                        if atr_stop > stop_loss:
                            stop_loss = atr_stop
                    elif trade.direction < 0:
                        if atr_stop < stop_loss:
                            stop_loss = atr_stop

                    # @todo could be done more precisely at certain time, not at any price change

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
                    #     trade.cancel_open(trader, self.instrument)
                    #     # logger.info("Canceled order (exit signal or entry timeout) %s" % (self.instrument.market_id,))
                    #     continue

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

                    #
                    # dynamic take-profit update
                    #

                    # @todo if the trend is weaker, lower the target distance, or if the trend stronger could increase to a largest one

                    if trade.is_opened() and not trade.is_valid(timestamp, trade.timeframe):
                        # @todo re-adjust entry
                        logger.info("Update order %s trade %s TODO" % (trade.id, self.instrument.market_id,))
                        continue

                    # only for active and currently not closing trades
                    if not trade.is_active() or trade.is_closing() or trade.is_closed():
                        continue

                    if retained_exit:
                        # exit the trade
                        self.process_exit(timestamp, trade, retained_exit.price)

        # update actives trades
        self.update_trades(timestamp)

        # retained long entry do the order entry signal
        for signal in retained_entries:
            # @todo problem want only in live mode, not during backtesting
            height = 0

            # @todo or trade at order book, compute the limit price from what the order book offer or could use ATR
            signal_price = signal.price + height

            if not self.process_entry(timestamp, signal.dir, signal_price, signal.tp, signal.sl, signal.timeframe):
                # notify a signal only
                self.notify_signal(timestamp, signal)

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

        if self.hedging:
            order_hedging = True

        # simply set the computed quantity
        order_quantity = quantity
        order_type = Order.ORDER_MARKET  #  Order.ORDER_LIMIT @todo limit later

        # @todo or trade at order book, compute the limit price from what the order book offer
        # limit best price at tiniest ofr price

        # adjust price to min / tick size / max
        order_price = self.instrument.adjust_price(price)

        if take_profit > 0:
            take_profit = self.instrument.adjust_price(take_profit)

        if stop_loss > 0:
            stop_loss = self.instrument.adjust_price(stop_loss)

        #
        # cancelation of the signal
        #

        if not self.check_min_notional(order_quantity, order_price):
            return False

        if self.has_max_trades(self.max_trades):
            return False
 
        #
        # execution of the order
        #

        trade = StrategyPositionTrade(timeframe)

        # the new trade must be in the trades list if the event comes before, and removed after only it failed
        self.add_trade(trade)

        if trade.open(trader, self.instrument, direction, order_type, order_price, order_quantity, take_profit, stop_loss, order_leverage, hedging=order_hedging):
            # initiate the take-profit limit order
            if take_profit > 0:
                trade.modify_take_profit(trader, self.instrument, take_profit)

            # # initiate the stop-loss order
            # if stop_loss > 0:
            #     trade.modify_stop_loss(trader, self.instrument, stop_loss)

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
        result = trade.close(trader, self.instrument) > 0
        trade.exit_reason = trade.REASON_CLOSE_MARKET

        return result

    #### @deprecated scorify method kept for history reference.
        # is_div = False
        # cross_dir = 0

        # msf = self.minor.score_ratio
        # Msf = self.major.score_ratio      

        # # initial confidence level
        # self.scorify.scale(self.score_confidence_level)

        # # detect if scores crosses
        # pm = self.minor.score.prev*msf
        # pM = self.minor.score.prev*Msf
        # nm = self.minor.score.last*msf
        # nM = self.major.score.last*Msf

        # # scores trends
        # mt = self.minor.score.trend_extremum()
        # Mt = self.major.score.trend_extremum()

        # is_div = utils.divergence(mt, Mt)
        # cross_dir = utils.cross((pm, pM), (nm, nM))

        # # accum until execution or cancelation
        # if is_div:
        #   # divergence from minor and major
        #   if self.score_div_factor[0] != 0.0:
        #       self.scorify.scale(self.score_div_factor[0])

        #   self.scorify.add(nm, self.score_div_factor[1])
        #   self.scorify.add(nM, self.score_div_factor[2])

        # elif cross_dir != 0.0:
        #   # score trend cross change or reinforcement, depend of the cross direction
        #   if self.score_cross_factor[0] != 0.0:
        #       self.scorify.scale(self.score_cross_factor[0])

        #   # @todo need 4 values ! need use the ConditionnalScore
        #   if cross_dir > 0:
        #       self.scorify.add(nm, self.score_cross_factor[1]*1.25)
        #       self.scorify.add(nM, self.score_cross_factor[2]*0.75)
        #   else:  # < 0
        #       self.scorify.add(nm, self.score_cross_factor[1]*1.0)
        #       self.scorify.add(nM, self.score_cross_factor[2]*1.0)

        #   # # or equivalent (all coef at 1.0)
        #   # self.scorify.add(nm, self.score_cross_factor[1])
        #   # self.scorify.add(nM, self.score_cross_factor[2])

        #   # 1.0 1.0    1.0 1.0 => 1340+?unpl
        #   # 1.25 0.75    0.75 1.25 => 1300+17
        #   # 1.25 0.75    1.0 1.0 => 1352+14  -> winner
        #   # 1.0 1.0    0.75 1.25 => 1290+14
        # else:
        #   # stay in the trend major+minor @todo default-score-ratio
        #   if self.score_default_factor[0] != 0.0:
        #       self.scorify.scale(self.score_default_factor[0])

        #   self.scorify.add(nm, self.score_default_factor[1])
        #   self.scorify.add(nM, self.score_default_factor[2])

        # self.scorify.finalize()

        # if self.scorify.has_signal and self.scorify.buy_or_sell > 0:
        #     do_entry = True

    ### older process_entry
        # positions = trader.positions(self.instrument.market_id)

        # # it is more secure to close opposite position before, for the case of the broker is in hedging mode
        # # and because of some issue got with ig.com
        # current_opposite_qty = 0.0
        # current_same_qty = 0.0

        # # @todo humm with the new trade mecanism...
        # for position in positions:
        #     # strategy does a reversal (and quantity are always positives)
        #     if position.direction != direction:
        #         # have in opposite directions ? close them !
        #         current_opposite_qty += position.quantity
        #         trader.close_position(position.position_id)
        #     else:
        #         # or same direction ?
        #         current_same_qty += position.quantity

        # if self.pyramided > 1:
        #     # max pyramided positions
        #     if quantity * self.pyramided < current_same_qty:
        #         # open while the max of pyramided * quantity is not reached
        #         order_quantity = quantity
        # else:
        #     if current_same_qty == 0:
        #         # open only if there is not others positions in the same direction
        #         order_quantity = quantity       
