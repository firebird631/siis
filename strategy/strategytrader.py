# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy trader base class.

import threading
import time

from strategy.strategytrade import StrategyTrade
from strategy.strategyassettrade import StrategyAssetTrade
from strategy.strategymargintrade import StrategyMarginTrade
from strategy.strategyindmargintrade import StrategyIndMarginTrade
from terminal.terminal import Terminal
from common.utils import timeframe_to_str
from notifier.signal import Signal

from trader.order import Order

import logging
logger = logging.getLogger('siis.strategy')


class StrategyTrader(object):
    """
    A strategy can manage multiple instrument. Strategy trader is on of the managed instruments.
    """

    def __init__(self, strategy, instrument):
        self.strategy = strategy
        self.instrument = instrument
        self.trades = []
        self._mutex = threading.RLock()
        self._next_trade_id = 1

        self._global_streamer = None
        self._timeframe_streamers = {}
        self._stats = {
            'perf': 0.0,     # initial
            'worst': 0.0,    # worst trade lost
            'best': 0.0,     # best trade profit
            'failed': [],    # failed terminated trades
            'success': [],   # success terminated trades
            'roe': [],       # return to equity trades
        }

    def lock(self, blocking=True, timeout=-1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    def create_chart_streamer(self, timeframe):
        """
        Create a streamer for the chart at a specific timeframe.
        Must be overrided.
        """
        return None

    def subscribe(self, timeframe):
        """
        Use or create a specific streamer.
        """
        if timeframe in self._timeframe_streamers:
            self._timeframe_streamers[timeframe].use()
            return True
        else:
            streamer = self.create_chart_streamer(timeframe)

            if streamer:
                streamer.use()
                self._timeframe_streamers[timeframe] = streamer
                return True

        return False

    def unsubscribe(self, timeframe):
        """
        Delete a specific streamer when no more subscribers.
        """
        if timeframe in self._timeframe_streamers:
            self._timeframe_streamers[timeframe].unuse()
            if self._timeframe_streamers[timeframe].is_free():
                # delete if 0 subscribers
                del self._timeframe_streamers[timeframe]
    
            return True
        else:
            return False

    def stream_call(self):
        """
        Process the call for the strategy trader. Must be overriden.
        """
        pass

    def process(self, tf, timestamp):
        """
        @param tf Smallest updated time unit.
        @param timestamp Current timestamp (or past time in backtest)
        """
        pass

    def order_signal(self, signal_type, data):
        """
        Update quantity/filled on a trade, deleted or canceled.
        """
        self.lock()

        try:
            for trade in self.trades:
                # update each trade relating the order (might be a unique)
                order_id = data[1]['id'] if type(data[1]) is dict else data[1]
                ref_order_id = data[2] if (len(data) > 2 and type(data[2]) is str) else None

                if trade.is_target_order(order_id, ref_order_id):   
                    trade.order_signal(signal_type, data[1], data[2] if len(data) > 2 else None)

        except Exception as e:
            logger.error(repr(e))

        self.unlock()

    def position_signal(self, signal_type, data):
        """
        Update quantity/filled on a trade, delete or cancel.
        """
        self.lock()

        try:
            for trade in self.trades:
                # update each trade relating the position (could be many)
                position_id = data[1]['id'] if type(data[1]) is dict else data[1]
                ref_order_id = data[2] if (len(data) > 2 and type(data[2]) is str) else None

                if trade.is_target_position(position_id, ref_order_id):
                    trade.position_signal(signal_type, data[1], data[2] if len(data) > 2 else None)

        except Exception as e:
            logger.error(repr(e))

        self.unlock()

    def add_trade(self, trade):
        """
        Add a new trade.
        """
        if not trade:
            return False

        self.lock()

        trade.id = self._next_trade_id
        self._next_trade_id += 1

        self.trades.append(trade)
        self.unlock()

    def remove_trade(self, trade):
        """
        Remove an existing trade.
        """
        if not trade:
            return False

        self.lock()
        self.trades.remove(trade)
        self.unlock()

    def update_timeout(self, timestamp, trade):
        """
        Aadjust the take-profit to current price (bid or ofr)
        and the stop-loss very tiny to protect the issue of the trade, when
        the trade arrives to a validity expiration. Mostly depend ofthe timeframe of
        the trade.
        """
        if not trade:
            return False

        if not trade.is_opened() or trade.is_closing() or trade.is_closed():
            return False

        MAX_TIME_UNIT = 18

        # more than max time unit of the timeframe then abort the trade
        if (trade.created_time > 0) and ((timestamp - trade.created_time) / trade.timeframe) > MAX_TIME_UNIT:
            # trade.modify_stop_loss()
            # trade.modify_take_profit()
            
            # this will exit now but prefer exit at limit and use a tiny stop
            trade.tp = self.instrument.close_exec_price(trade.dir)
            trade.sl = self.instrument.close_exec_price(trade.dir)

            logger.info("> Trade %s timeout !" % trade.id)

        return True

    def update_trades(self, timestamp):
        """
        Update managed trades per instruments and delete terminated trades.
        """
        if not self.strategy.activity:
            return

        if not self.trades:
            return

        trader = self.strategy.trader()

        #
        # for each trade check if the TP or SL is reached and trigger if necessary
        #

        self.lock()

        for trade in self.trades:

            #
            # managed operation
            #

            if trade.has_operations():
                mutated = False

                for operation in trade.operations:
                    mutated |= operation.test_and_operate(trade, self.instrument, trader)

                if mutated:
                    trade.cleanup_operations()

            #
            # active trade
            #

            if trade.is_active():
                self.update_timeout(timestamp, trade)

                # for statistics usage
                trade.update_stats(self.instrument.close_exec_price(trade.direction), timestamp)

            #
            # asset trade
            #

            if trade.trade_type == StrategyTrade.TRADE_BUY_SELL:
                if trade.is_closed():
                    continue

                # process only on active trades
                if not trade.is_active():
                    # @todo timeout if not filled before condition...
                    continue

                if trade.is_closing():
                    continue

                # potential order exec close price (always close a long)
                close_exec_price = self.instrument.close_exec_price(Order.LONG)

                if trade.tp > 0 and (close_exec_price >= trade.tp):
                    # take profit order
                    # @todo or limit order for maker fee
                    # trade.modify_take_profit(trader, market, take_profit)
                    # close at market (taker fee)
                    if trade.close(trader, self.instrument.market_id):
                        self._global_streamer.member('buy-exit').update(close_exec_price, timestamp)

                    # only get it at the last moment
                    market = trader.market(self.instrument.market_id)

                    # estimed profit/loss rate
                    profit_loss_rate = (close_exec_price - trade.p) / trade.p

                    # estimed maker/taker fee rate for entry and exit
                    if trade.get_stats()['entry-maker']:
                        profit_loss_rate -= market.maker_fee
                    else:
                        profit_loss_rate -= market.taker_fee

                    if trade.get_stats()['exit-maker']:
                        profit_loss_rate -= market.maker_fee
                    else:
                        profit_loss_rate -= market.taker_fee

                    text = "%s take-profit-market %s %.2f%% on %s (%.4f%s) at %s" % (
                        self.strategy.identifier, market.symbol, profit_loss_rate*100.0, market.base,
                        profit_loss_rate/market.base_exchange_rate, trader.account.currency_display, market.format_price(close_exec_price))

                    Terminal.inst().high(text, view='common') if profit_loss_rate > 0 else Terminal.inst().low(text, view='common')

                    # notify
                    self.strategy.notify_order(trade.id, Order.SHORT, self.instrument.market_id,
                            market.format_price(close_exec_price), timestamp, trade.timeframe,
                            'take-profit', profit_loss_rate)

                elif trade.sl > 0 and (close_exec_price <= trade.sl):
                    # stop loss order
                    # close at market (taker fee)
                    if trade.close(trader, self.instrument.market_id):
                        self._global_streamer.member('buy-exit').update(close_exec_price, timestamp)

                    # only get it at the last moment
                    market = trader.market(self.instrument.market_id)

                    # estimed profit/loss rate
                    profit_loss_rate = (close_exec_price - trade.p) / trade.p

                    # estimed maker/taker fee rate for entry and exit
                    if trade.get_stats()['entry-maker']:
                        profit_loss_rate -= market.maker_fee
                    else:
                        profit_loss_rate -= market.taker_fee

                    if trade.get_stats()['exit-maker']:
                        profit_loss_rate -= market.maker_fee
                    else:
                        profit_loss_rate -= market.taker_fee

                    text = "%s stop-market %s %.2f%% %s (%.4f%s) at %s" % (
                        self.strategy.identifier, market.symbol, profit_loss_rate*100.0, market.base,
                        profit_loss_rate/market.base_exchange_rate, trader.account.currency_display, market.format_price(close_exec_price))

                    Terminal.inst().high(text, view='common') if profit_loss_rate > 0 else Terminal.inst().low(text, view='common')

                    # notify
                    self.strategy.notify_order(trade.id, Order.SHORT, self.instrument.market_id,
                            market.format_price(close_exec_price), timestamp, trade.timeframe,
                            'stop-loss', profit_loss_rate)

            #
            # margin trade
            #

            elif trade.trade_type == StrategyTrade.TRADE_MARGIN or trade.trade_type == StrategyTrade.TRADE_IND_MARGIN:
                # process only on active trades
                if not trade.is_active():
                    # @todo timeout if not filled before condition...
                    continue

                if trade.is_closed():
                    continue

                if trade.is_closing():
                    continue

                if not self.instrument.market_open:
                    continue

                # potential order exec close price
                close_exec_price = self.instrument.close_exec_price(trade.direction)

                if (trade.tp > 0) and (trade.direction > 0 and close_exec_price >= trade.tp) or (trade.direction < 0 and close_exec_price <= trade.tp):
                    # close in profit at market (taker fee)
                    if trade.close(trader, self.instrument.market_id):
                        # only get it at the last moment
                        market = trader.market(self.instrument.market_id)

                        # estimed profit/loss rate
                        if trade.direction > 0 and trade.p:
                            profit_loss_rate = (close_exec_price - trade.p) / trade.p
                        elif trade.direction < 0 and trade.p:
                            profit_loss_rate = (trade.p - close_exec_price) / trade.p
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

                        # and notify
                        self.strategy.notify_order(trade.id, trade.close_direction(), self.instrument.market_id,
                                market.format_price(close_exec_price), timestamp, trade.timeframe,
                                'take-profit', profit_loss_rate)

                        # close a long or a short position at take-profit level
                        text = "%s take-profit-market %s %.4f%s (%.4f) at %s" % (
                            self.strategy.identifier, market.symbol, profit_loss_rate*100.0, market.quote,
                            profit_loss_rate/market.base_exchange_rate, market.format_price(close_exec_price))

                        Terminal.inst().high(text, view='common') if profit_loss_rate > 0 else Terminal.inst().low(text, view='common')

                    # and for streaming
                    self._global_streamer.member('buy-exit').update(close_exec_price, timestamp)

                elif (trade.sl > 0) and (trade.direction > 0 and close_exec_price <= trade.sl) or (trade.direction < 0 and close_exec_price >= trade.sl):
                    # close a long or a short position at stop-loss level at market (taker fee)
                    if trade.close(trader, self.instrument.market_id):
                        # only get it at the last moment
                        market = trader.market(self.instrument.market_id)

                        # estimed profit/loss rate
                        if trade.direction > 0 and trade.p:
                            profit_loss_rate = (close_exec_price - trade.p) / trade.p
                        elif trade.direction < 0 and trade.p:
                            profit_loss_rate = (trade.p - close_exec_price) / trade.p
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

                        # and notify
                        self.strategy.notify_order(trade.id, trade.close_direction(), self.instrument.market_id,
                                market.format_price(close_exec_price), timestamp, trade.timeframe,
                                'stop-loss', profit_loss_rate)

                        text = "%s stop-market %s %.4f%s (%.4f) at %s" % (
                            self.strategy.identifier, market.symbol, profit_loss_rate, market.quote,
                            profit_loss_rate/market.base_exchange_rate, market.format_price(close_exec_price))

                        Terminal.inst().high(text, view='common') if profit_loss_rate > 0 else Terminal.inst().low(text, view='common')

                    # and for streaming                            
                    self._global_streamer.member('sell-exit').update(close_exec_price, timestamp)

        self.unlock()

        #
        # remove terminated, rejected, canceled and empty trades
        #

        rm_list = []

        self.lock()

        for trade in self.trades:
            if trade.can_delete():
                # cleanup if necessary before deleting the trade related refs, and add them to the deletion list
                trade.remove(trader)
                rm_list.append(trade)

                # record the trade for analysis and learning
                if not trade.is_canceled():
                    # estimation on mid last price, but might be close market price
                    market = trader.market(self.instrument.market_id)

                    rate = trade.pl

                    # estimed maker/taker fee rate for entry and exit
                    if trade._stats['entry-maker']:
                        rate -= market.maker_fee
                    else:
                        rate -= market.taker_fee

                    if trade._stats['exit-maker']:
                        rate -= market.maker_fee
                    else:
                        rate -= market.taker_fee

                    # estimed commission fee rate
                    # @todo

                    # perf sommed here it means that its not done during partial closing
                    if rate != 0.0:
                        self._stats['perf'] += rate
                        self._stats['worst'] = min(self._stats['worst'], rate)
                        self._stats['best'] = max(self._stats['best'], rate)

                    record = {
                        'id': trade.id,
                        'ts': trade.t,
                        'd': trade.direction_to_str(),
                        'p': market.format_price(trade.p),
                        'q': market.format_quantity(trade.q),
                        'e': market.format_quantity(trade.e),
                        'x': market.format_quantity(trade.x),
                        'tp': market.format_price(trade.tp),
                        'sl': market.format_price(trade.sl),
                        'rate': rate,
                        'tf': timeframe_to_str(trade.timeframe),
                        's': trade.state_to_str(),
                        'c': trade.conditions,
                        'b': market.format_price(trade.best_price()),
                        'w': market.format_price(trade.worst_price()),
                        'bt': trade.best_price_timestamp(),
                        'wt': trade.worst_price_timestamp(),
                    }

                    if rate < 0:
                        self._stats['failed'].append(record)
                    elif rate > 0:
                        self._stats['success'].append(record)
                    else:
                        self._stats['roe'].append(record)

        # delete terminated trades
        for trade in rm_list:
            self.trades.remove(trade)

        self.unlock()

    def update_trailing_stop(self, trade, market):
        """
        Update the stop price of a trade using a simple level distance or percent distance method.

        @note This method is not a way to process a stop, it mostly failed, close for nothing at a wrong price.
        """
        close_exec_price = market.price  #  market.close_exec_price(trade.direction)
        stop_loss = trade.sl

        if trade.direction > 0:
            # long case
            pass

            # ratio = close_exec_price / trade.p
            # sl_ratio = (trade.p - trade.sl) / trade.p
            # dist = (close_exec_price - trade.sl) / trade.p
            # step = 0.01  # 1% trailing stop-loss

            # # # @todo take a stop-loss from a timeframe level
            # # # profit >= 1% up the stop-loss
            # # if dist > (sl_ratio + step):
            # #     stop_loss = close_exec_price * (1.0 - sl_ratio)
            # #     logger.debug("update SL from %s to %s" % (trade.sl, stop_loss))

            # # # protect from loss when a trade become profitable
            # # # not a good idea because it depend of the volatility
            # # if ratio >= 1.01:
            # #     stop_loss = max(stop_loss, trade.p)  # at 1% profit stop at break-even
            
            # # # alternative @todo how to trigger
            # # if ratio >= 1.10:
            # #     stop_loss = max(trade.sl, close_exec_price - (close_exec_price/trade.p*(close_exec_price-trade.p)*0.33))

            # # ultra large and based on the distance of the price
            # # if dist > 0.25:
            # #     stop_loss = trade.p + (trade.p * (dist * 0.5))

            # # if stop_loss != trade.sl:
            # #     logger.info("update SL from %s to %s (market price %s)" % (trade.sl, stop_loss, market.price))
            # #     # trade.modify_stop_loss(trader, market.market_id, stop_loss)
            # #     trade.sl = stop_loss

        elif trade.direction < 0:
            # short case
            pass
