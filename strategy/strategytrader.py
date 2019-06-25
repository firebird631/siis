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

    @todo _global_streamer must be improved. streaming functionnalities must be only connected to the
        notification receiver (only then keep notify_order calls), streaming will be done on a distinct service.
        disable any others streaming capacities on the sub-traders excepted for debug purposes.
    """

    MAX_TIME_UNIT = 18  # number of timeframe unit for a trade expiry, default to 18 units

    def __init__(self, strategy, instrument):
        self.strategy = strategy
        self.instrument = instrument

        self.trades = []
        self.regions = []

        self._next_trade_id = 1
        self._next_region_id = 1

        self._mutex = threading.RLock()
        self._activity = True

        self._expiry_max_time_unit = StrategyTrader.MAX_TIME_UNIT

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

    @property
    def activity(self):
        return self._activity

    def set_activity(self, status):
        """
        Enable/disable execution of the automated orders.
        """
        self._activity = status   

    def process(self, timeframe, timestamp):
        """
        Override this method to do her all the strategy work. You must call the update_trades method
        during the process.

        @param timeframe Update timeframe unit.
        @param timestamp Current timestamp (or past time in backtest).
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

    def update_timeout(self, timestamp, trade, local=True):
        """
        Aadjust the take-profit to current price (bid or ofr) and the stop-loss very tiny to protect the issue of the trade,
        when the trade arrives to a validity expiration. Mostly depend ofthe timeframe of the trade.
        """
        if not trade:
            return False

        if not trade.is_opened() or trade.is_closing() or trade.is_closed():
            return False

        # more than max time unit of the timeframe then abort the trade
        if (trade.created_time > 0) and ((timestamp - trade.created_time) / trade.timeframe) > self._expiry_max_time_unit:
            if local:
                trade.tp = self.instrument.close_exec_price(trade.dir)
                trade.sl = self.instrument.close_exec_price(trade.dir)
            else:
                trade.modify_stop_loss()
                trade.modify_take_profit()

        return True

    def update_trades(self, timestamp):
        """
        Update managed trades per instruments and delete terminated trades.
        """
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

                if not self.instrument.market_open:
                    continue

                # potential order exec close price (always close a long)
                close_exec_price = self.instrument.close_exec_price(Order.LONG)

                if trade.tp > 0 and (close_exec_price >= trade.tp):
                    # take profit order
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

                        # and for streaming
                        self._global_streamer.member('sell-exit' if trade.direction < 0 else 'buy-exit').update(close_exec_price, timestamp)

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

                        # and for streaming
                        self._global_streamer.member('sell-exit' if trade.direction < 0 else 'buy-exit').update(close_exec_price, timestamp)

        self.unlock()

        #
        # remove terminated, rejected, canceled and empty trades
        #

        mutated = False

        self.lock()

        for trade in self.trades:
            if trade.can_delete():
                mutated = True

                # cleanup if necessary before deleting the trade related refs, and add them to the deletion list
                trade.remove(trader)

                # record the trade for analysis and learning
                if not trade.is_canceled():
                    # @todo all this part could be in an async method of another background service, because 
                    # it is not part of the trade managemnt neither strategy computing, its purely for reporting
                    # and view
                    # then we could add a list of the deleted trade (producer) and having another service (consumer)
                    # doing the rest

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

        # recreate the list of trades
        if mutated:
            trades_list = []

            for trade in self.trades:
                if not trade.can_delete():
                    # keep only active and pending trades
                    trades_list.append(trade)

            self.trades = trades_list

        self.unlock()

    #
    # region management
    #

    def add_region(self, region):
        self.lock()
        region.set_id(self._next_region_id)
        self._next_region_id += 1
        self.regions.append(region)
        self.unlock()

    def remove_region(self, region_id):
        self.lock()

        for region in self.regions:
            if region.id == region_id:
                self.regions.remove(region)
                break

        self.unlock()

    def check_regions(self, signal):
        """
        Compare a signal to defined regions if somes are defineds.
        @note This method is not trade safe.
        """
        if self.regions:
            # one ore many region, have to pass at least one test
            for region in self.regions:
                if region.test_region(signal):
                    return True

            return False
        else:
            # no region always pass
            return True

    #
    # miscs
    #

    def update_trailing_stop(self, trade, market, distance, local=True, distance_in_percent=True):
        """
        Update the stop price of a trade using a simple level distance or percent distance method.
        @param local boolean True mean only modify the stop-loss price on this side,
            not on the position or on the stop order

        @note This method is not a way to process a stop, it mostly failed, close for nothing at a wrong price.
        """
        close_exec_price = market.price  #  market.close_exec_price(trade.direction)
        stop_loss = trade.sl

        if trade.direction > 0:
            # long case
            ratio = close_exec_price / trade.p
            sl_ratio = (trade.p - trade.sl) / trade.p
            dist = (close_exec_price - trade.sl) / trade.p
            step = distance

            if distance_in_percent:
                # @todo
                if dist > (sl_ratio + step):
                    stop_loss = close_exec_price * (1.0 - distance)
            else:
                # @todo
                pass

            # # if dist > (sl_ratio + step):
            # #     stop_loss = close_exec_price * (1.0 - sl_ratio)
            # #     logger.debug("update SL from %s to %s" % (trade.sl, stop_loss))

            # # # alternative @todo how to trigger
            # # if ratio >= 1.10:
            # #     stop_loss = max(trade.sl, close_exec_price - (close_exec_price/trade.p*(close_exec_price-trade.p)*0.33))

            # # ultra large and based on the distance of the price
            # # if dist > 0.25:
            # #     stop_loss = trade.p + (trade.p * (dist * 0.5))

        elif trade.direction < 0:
            # short case
            ratio = close_exec_price / trade.p
            sl_ratio = (trade.sl - trade.p) / trade.p
            dist = (trade.sl - close_exec_price) / trade.p
            step = distance

            if distance_in_percent:
                # @todo
                if dist > (sl_ratio - step):
                    stop_loss = close_exec_price * (1.0 - distance)
                pass
            else:
                # @todo
                pass

        if stop_loss != trade.sl:
            if local:
                trade.sl = stop_loss
            else:
                trade.modify_stop_loss(trader, market.market_id, stop_loss)

    #
    # signal data streaming
    #

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
