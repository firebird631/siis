# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy trader base class.

import pathlib
import threading
import time

from datetime import datetime

from strategy.strategyassettrade import StrategyAssetTrade
from strategy.strategyindmargintrade import StrategyIndMarginTrade
from strategy.strategymargintrade import StrategyMarginTrade
from strategy.strategypositiontrade import StrategyPositionTrade
from strategy.strategytrade import StrategyTrade

from strategy.indicator.models import Limits

from instrument.instrument import Instrument

from common.utils import timeframe_to_str, UTC
from common.signal import Signal
from terminal.terminal import Terminal

from database.database import Database
from trader.order import Order

import logging
logger = logging.getLogger('siis.strategy.trader')
error_logger = logging.getLogger('siis.error.strategy.trader')


class StrategyTrader(object):
    """
    A strategy can manage multiple instrument. Strategy trader is on of the managed instruments.
    """

    MARKET_TYPE_MAP = {
        'asset': Instrument.TRADE_SPOT,
        'spot': Instrument.TRADE_SPOT,
        'margin': Instrument.TRADE_MARGIN,
        'position': Instrument.TRADE_POSITION,
        'ind-margin': Instrument.TRADE_IND_MARGIN,
    }

    REPORTING_NONE = 0
    REPORTING_VERBOSE = 1

    REPORTING_MAP = {
        'none': REPORTING_NONE,
        'verbose': REPORTING_VERBOSE,
    }

    def __init__(self, strategy, instrument):
        self.strategy = strategy
        self.instrument = instrument

        self._mutex = threading.RLock()  # activity, global locker, region locker, instrument locker
        self._activity = True
        self._affinity = 5          # based on a linear scale [0..10]

        self._limits = Limits()     # price and timestamp ranges

        self._preprocessing = 1     # 1 waited, 2 to 4 in progress, 0 normal
        self._preprocess_depth = 0  # in second, need of preprocessed data depth of history
        self._preprocess_streamer = None       # current tick or quote streamer
        self._preprocess_from_timestamp = 0.0  # preprocessed date from this timestamp to limit last timestamp

        self._bootstraping = 1      # 1 waited, 2 in progress, 0 normal, done from loaded OHLCs history

        self._processing = False   # True during processing

        self._trade_mutex = threading.RLock()   # trades locker
        self._trades = []
        self._next_trade_id = 1

        self._regions = []
        self._next_region_id = 1

        self._alerts = []
        self._next_alert_id= 1

        self._global_streamer = None
        self._trade_entry_streamer = None
        self._trade_update_streamer = None
        self._trade_exit_streamer = None
        self._signal_streamer = None
        self._alert_streamer = None

        self._reporting = StrategyTrader.REPORTING_NONE

        self._stats = {
            'perf': 0.0,       # initial
            'worst': 0.0,      # worst trade lost
            'best': 0.0,       # best trade profit
            'worst-sum': 0.0,  # sum of worst trade lost
            'best-sum': 0.0,   # sum of best trade profit
            'failed': [],      # failed terminated trades
            'success': [],     # success terminated trades
            'roe': [],         # return to equity trades
            'cont-win': 0,     # contigous win trades
            'cont-loss': 0,    # contigous loss trades
        }

    #
    # properties
    #

    @property
    def is_timeframes_based(self):
        return False

    @property
    def is_tickbars_based(self):
        return False

    #
    # processing
    #

    @property
    def activity(self):
        """
        Strategy trader Local state.
        """
        return self._activity

    def set_activity(self, status):
        """
        Enable/disable execution of the automated orders.
        """
        self._activity = status

    @property
    def affinity(self):
        """
        Strategy trader affinity rate.
        """
        return self._affinity

    @affinity.setter
    def affinity(self, affinity):
        """
        Set strategy trader affinity rate.
        """
        self._affinity = affinity

    #
    # pre-processing
    #

    def preprocess_load_cache(self, from_date, to_date):
        """
        Override this method to load the cached data before performing preprocess.
        """
        pass

    def preprocess(self, trade):
        """
        Override this method to preprocess trade per trade each most recent data than the cache.
        """
        pass

    def preprocess_store_cache(self, from_date, to_date):
        """
        Override this method to store in cache the preprocessed data.
        """
        pass   

    #
    # processing
    #

    def prepare(self):
        """
        Prepare before entering live or backtest data stream.
        Prepare indicators, signals states and flags.

        It is called before bootstrap iterations and before process iterations.
        """
        pass

    def bootstrap(self, timestamp):
        """
        Override this method to do all the initial strategy work using the preloaded OHLCs history.
        No trade must be done here, but signal pre-state could be computed.

        This is useful for strategies having pre trigger signal, in way to don't miss the comings
        signals validations.
        """
        pass

    def process(self, timeframe, timestamp):
        """
        Override this method to do her all the strategy work.
        You must call the update_trades method during the process in way to manage the trades.

        @param timeframe Update timeframe unit.
        @param timestamp Current timestamp (or in backtest the processed time in past).
        """
        pass

    def terminate(self):
        """
        Delete any non realized trades (new or open) or remaining closed but not closing.
        """
        trader = self.strategy.trader()
        mutated = False
        trades_list = []

        with self._mutex:
            with self._trade_mutex:
                for trade in self._trades:
                    if trade.can_delete() or not trade.is_active() or trade.is_closed():
                        mutated = True

                        # cleanup if necessary before deleting the trade related refs
                        trade.remove(trader, self.instrument)
                    else:
                        trades_list.append(trade)

                # updated trade list, the ones we would save
                if mutated:
                    self._trades = trades_list

    #
    # persistance
    #

    def save(self):
        """
        Trader and trades persistance (might occurs only for live mode on real accounts).
        @note Must be called only after terminate.
        """
        trader = self.strategy.trader()

        with self._mutex:
            with self._trade_mutex:
                for trade in self._trades:
                    t_data = trade.dumps()
                    ops_data = [operation.dumps() for operation in trade.operations]

                    # store per trade
                    Database.inst().store_user_trade((trader.name, trader.account.name, self.instrument.market_id,
                            self.strategy.identifier, trade.id, trade.trade_type, t_data, ops_data))

            # dumps of trader data, regions and alerts
            trader_data = {
                'affinity': self._affinity,
            }

            regions_data = [region.dumps() for region in self._regions]
            alerts_data = [alert.dumps() for alert in self._alerts]

            Database.inst().store_user_trader((trader.name, trader.account.name, self.instrument.market_id,
                    self.strategy.identifier, self.activity, trader_data, regions_data, alerts_data))

    def loads(self, data, regions, alerts):
        """
        Load strategy trader state and regions.
        """
        # data reserved
        if 'affinity' in data and type(data['affinity']) is int:
            self._affinity = data['affinity']

        # instanciates the regions
        for r in regions:
            if r['name'] in self.strategy.service.regions:
                try:
                    # instanciate the region
                    region = self.strategy.service.regions[r['name']](0, 0, 0, 0)
                    region.loads(r)

                    if region.check():
                        self.add_region(region)
                    else:
                        error_logger.error("During loads, region checking error %s" % (r['name'],))
                except Exception as e:
                    error_logger.error(repr(e))
            else:
                error_logger.error("During loads, unsupported region %s" % (r['name'],))

        # instanciates the alerts
        for a in alerts:
            if a['name'] in self.strategy.service.alerts:
                try:
                    # instanciate the alert
                    alert = self.strategy.service.alerts[a['name']](0, 0)
                    alert.loads(a)

                    if alert.check():
                        self.add_alert(alert)
                    else:
                        error_logger.error("During loads, alert checking error %s" % (a['name'],))
                except Exception as e:
                    error_logger.error(repr(e))
            else:
                error_logger.error("During loads, unsupported alert %s" % (a['name'],))

    def loads_trade(self, trade_id, trade_type, data, operations):
        """
        Load a strategy trader trade and its operations.
        @todo Need to check the validity of the trade :
            - existings orders, create, sell, limit, stop, position
            - and eventually the free margin, asset quantity
        There is many scenarii where the trade state changed, trade executed, order modified or canceled...
        """
        trade = None

        # trade builder
        if trade_type == StrategyTrade.TRADE_BUY_SELL:
            trade = StrategyAssetTrade(0)
        elif trade_type == StrategyTrade.TRADE_MARGIN:
            trade = StrategyMarginTrade(0)
        elif trade_type == StrategyTrade.TRADE_POSITION:
            trade = StrategyPositionTrade(0)
        elif trade_type == StrategyTrade.TRADE_IND_MARGIN:
            trade = StrategyIndMarginTrade(0)
        else:
            error_logger.error("During loads, usupported trade type %i" % (trade_type,))
            return

        trade.loads(data, self.strategy.service)

        # operations
        for op in operations:
            if op['name'] in self.strategy.service.tradeops:
                try:
                    operation = self.strategy.service.tradeops[op['name']]()
                    operation.loads(op)

                    if operation.check(trade):
                        # append the operation to the trade
                        trade.add_operation(operation)
                    else:
                        error_logger.error("During loads, operation checking error %s" % (op_name,))
                except Exception as e:
                    error_logger.error(repr(e))
            else:
                error_logger.error("During loads, region checking error %s" % (r['name'],))

        # check orders/position/quantity before adding
        trader = self.strategy.trader()

        if trade.check(trader, self.instrument):
            self.add_trade(trade)

    #
    # order/position slot
    #

    def order_signal(self, signal_type, data):
        """
        Update quantity/filled on a trade, deleted or canceled.
        """
        with self._trade_mutex:
            try:
                for trade in self._trades:
                    # update each trade relating the order (might be a unique)
                    order_id = data[1]['id'] if type(data[1]) is dict else data[1]
                    ref_order_id = data[2] if (len(data) > 2 and type(data[2]) is str) else None

                    if trade.is_target_order(order_id, ref_order_id):
                        trade.order_signal(signal_type, data[1], data[2] if len(data) > 2 else None, self.instrument)

            except Exception as e:
                error_logger.error(traceback.format_exc())
                error_logger.error(repr(e))

    def position_signal(self, signal_type, data):
        """
        Update quantity/filled on a trade, delete or cancel.
        """
        with self._trade_mutex:
            try:
                for trade in self._trades:
                    # update each trade relating the position (could be many)
                    position_id = data[1]['id'] if type(data[1]) is dict else data[1]
                    ref_order_id = data[2] if (len(data) > 2 and type(data[2]) is str) else None

                    if trade.is_target_position(position_id, ref_order_id):
                        trade.position_signal(signal_type, data[1], data[2] if len(data) > 2 else None, self.instrument)

            except Exception as e:
                error_logger.error(traceback.format_exc())
                error_logger.error(repr(e))

    #
    # trade
    #

    @property
    def trades(self):
        return self._trades

    def add_trade(self, trade):
        """
        Add a new trade.
        """
        if not trade:
            return False

        with self._trade_mutex:
            trade.id = self._next_trade_id
            self._next_trade_id += 1

            self._trades.append(trade)

    def remove_trade(self, trade):
        """
        Remove an existing trade.
        """
        if not trade:
            return False

        with self._trade_mutex:
            self._trades.remove(trade)

    def has_trades(self):
        """
        Is pending or active trades.
        """
        with self._trade_mutex:
            return len(self._trades) > 0

        return False

    def list_trades(self):
        """
        List of ids of pendings and actives trades.
        """
        results = []

        with self._trade_mutex:
            for trade in self._trades:
                results.append(trade.id)

        return results

    def dumps_trades_update(self):
        """
        Dumps the update notify state of each existings trades.
        """
        results = []

        with self._trade_mutex:
            for trade in self._trades:
                results.append(trade.dumps_notify_update(self.strategy.timestamp, self))

        return results

    def dumps_trades_history(self):
        """
        Dumps the historical record of each historical trades.
        """
        results = []

        with self._mutex:
            results = self._stats['success'] + self._stats['failed'] + self._stats['roe']

            # sort by entry timestamp desc
            results = sorted(results, key=lambda trade: -trade['eot'], reverse=True)

        return results

    def update_trades(self, timestamp):
        """
        Update managed trades per instruments and delete terminated trades.
        """
        if not self._trades:
            return

        trader = self.strategy.trader()

        #
        # for each trade check if the TP or SL is reached and trigger if necessary
        #

        with self._trade_mutex:
            for trade in self._trades:

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
                    # for statistics usage
                    trade.update_stats(self.instrument.close_exec_price(trade.direction), timestamp)

                    # update data stream
                    self.notify_trade_update(timestamp, trade)

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

                    if not self.instrument.tradeable:
                        continue

                    if trade.is_dirty:
                        # entry quantity changed need to update the exits orders
                        trade.update_dirty(trader, self.instrument)

                    # potential order exec close price (always close a long)
                    close_exec_price = self.instrument.close_exec_price(Order.LONG)

                    if (trade.tp > 0) and (close_exec_price >= trade.tp) and not trade.has_limit_order():
                        # take profit trigger stop, close at market (taker fee)
                        if trade.close(trader, self.instrument) > 0:
                            trade.exit_reason = trade.REASON_TAKE_PROFIT_MARKET

                    elif (trade.sl > 0) and (close_exec_price <= trade.sl) and not trade.has_stop_order():
                        # stop loss trigger stop, close at market (taker fee)
                        if trade.close(trader, self.instrument) > 0:
                            trade.exit_reason = trade.REASON_STOP_LOSS_MARKET

                #
                # margin trade
                #

                elif trade.trade_type in (StrategyTrade.TRADE_MARGIN, StrategyTrade.TRADE_POSITION, StrategyTrade.TRADE_IND_MARGIN):
                    # process only on active trades
                    if not trade.is_active():
                        # @todo timeout if not filled before condition...
                        continue

                    if trade.is_closed():
                        continue

                    if trade.is_closing():
                        continue

                    if not self.instrument.tradeable:
                        continue

                    if trade.is_dirty:
                        # entry quantity changed need to update the exits orders
                        trade.update_dirty(trader, self.instrument)

                    # potential order exec close price
                    close_exec_price = self.instrument.close_exec_price(trade.direction)

                    if (trade.tp > 0) and ((trade.direction > 0 and close_exec_price >= trade.tp) or (trade.direction < 0 and close_exec_price <= trade.tp)) and not trade.has_limit_order():
                        # close in profit at market (taker fee)
                        if trade.close(trader, self.instrument) > 0:
                            trade.exit_reason = trade.REASON_TAKE_PROFIT_MARKET

                    elif (trade.sl > 0) and ((trade.direction > 0 and close_exec_price <= trade.sl) or (trade.direction < 0 and close_exec_price >= trade.sl)) and not trade.has_stop_order():
                        # close a long or a short position at stop-loss level at market (taker fee)
                        if trade.close(trader, self.instrument) > 0:
                            trade.exit_reason = trade.REASON_STOP_LOSS_MARKET

        #
        # remove terminated, rejected, canceled and empty trades
        #

        mutated = False

        with self._trade_mutex:
            for trade in self._trades:
                if trade.can_delete():
                    mutated = True

                    # cleanup if necessary before deleting the trade related refs
                    trade.remove(trader, self.instrument)

                    # record the trade for analysis and study
                    if not trade.is_canceled():
                        # last update of stats before logging
                        trade.update_stats(self.instrument.close_exec_price(trade.direction), timestamp)

                        # realized profit/loss
                        profit_loss = trade.profit_loss - trade.entry_fees_rate() - trade.exit_fees_rate()

                        best_pl = (trade.best_price() - trade.entry_price if trade.direction > 0 else trade.entry_price - trade.best_price()) / trade.entry_price
                        worst_pl = (trade.worst_price() - trade.entry_price if trade.direction > 0 else trade.entry_price - trade.worst_price()) / trade.entry_price

                        # perf sommed here it means that its not done during partial closing
                        if profit_loss != 0.0:
                            self._stats['perf'] += profit_loss
                            self._stats['best'] = max(self._stats['best'], profit_loss)
                            self._stats['best-sum'] += best_pl
                            self._stats['worst'] = min(self._stats['worst'], profit_loss)
                            self._stats['worst-sum'] += worst_pl

                        if profit_loss <= 0.0:
                            self._stats['cont-loss'] += 1
                            self._stats['cont-win'] = 0

                        elif profit_loss > 0.0:
                            self._stats['cont-loss'] = 0
                            self._stats['cont-win'] += 1

                        # keep for historical @todo harmonize using this record (remove the next)
                        # record = trade.dumps_notify_exit(timestamp, self)

                        record = {
                            'id': trade.id,
                            'mid': self.instrument.market_id,
                            'eot': trade.entry_open_time,
                            'xot': trade.exit_open_time,
                            'freot': trade.first_realized_entry_time,
                            'frxot': trade.first_realized_exit_time,
                            'lreot': trade.last_realized_entry_time,
                            'lrxot': trade.last_realized_exit_time,
                            'd': trade.direction_to_str(),
                            't': trade.entry_order_type_to_str(),
                            'l': self.instrument.format_price(trade.order_price),
                            'q': self.instrument.format_quantity(trade.order_quantity),
                            'e': self.instrument.format_quantity(trade.exec_entry_qty),
                            'x': self.instrument.format_quantity(trade.exec_exit_qty),
                            'tp': self.instrument.format_price(trade.take_profit),
                            'sl': self.instrument.format_price(trade.stop_loss),
                            'tf': timeframe_to_str(trade.timeframe),
                            'aep': self.instrument.format_price(trade.entry_price),
                            'axp': self.instrument.format_price(trade.exit_price),
                            's': trade.state_to_str(),
                            'b': self.instrument.format_price(trade.best_price()),
                            'w': self.instrument.format_price(trade.worst_price()),
                            'bt': trade.best_price_timestamp(),
                            'wt': trade.worst_price_timestamp(),
                            'pl': profit_loss,
                            'fees': trade.entry_fees_rate() + trade.exit_fees_rate(),
                            'c': trade.get_conditions(),
                            'label': trade.label,
                            'rpnl': self.instrument.format_price(trade.unrealized_profit_loss),  # once close its realized
                            'pnlcur': trade.profit_loss_currency
                        }

                        if profit_loss < 0:
                            self._stats['failed'].append(record)
                        elif profit_loss > 0:
                            self._stats['success'].append(record)
                        else:
                            self._stats['roe'].append(record)

                        if self._reporting == StrategyTrader.REPORTING_VERBOSE:
                            try:
                                self.report(trade, False)
                            except Exception as e:
                                error_logger.error(str(e))

                        # notification exit reason if not reported
                        if not trade.exit_reason:
                            if trade.direction > 0:
                                if trade.exit_price >= trade.take_profit and trade.take_profit > 0:
                                    trade.exit_reason = trade.REASON_TAKE_PROFIT_LIMIT
                                elif trade.exit_price <= trade.stop_loss and trade.stop_loss > 0:
                                    trade.exit_reason = trade.REASON_STOP_LOSS_MARKET
                            elif trade.direction < 0:
                                if trade.exit_price <= trade.take_profit and trade.take_profit > 0:
                                    trade.exit_reason = trade.REASON_TAKE_PROFIT_LIMIT
                                elif trade.exit_price >= trade.stop_loss and trade.stop_loss > 0:
                                    trade.exit_reason = trade.REASON_STOP_LOSS_MARKET

                        trade.pl = profit_loss

                        self.notify_trade_exit(timestamp, trade)
                    else:
                        if not trade.exit_reason:
                            trade.exit_reason = trade.REASON_CANCELED_TIMEOUT

                        self.notify_trade_exit(timestamp, trade)

            # recreate the list of trades
            if mutated:
                trades_list = []

                for trade in self._trades:
                    if not trade.can_delete():
                        # keep only active and pending trades
                        trades_list.append(trade)

                self._trades = trades_list

    def on_received_liquidation(self, liquidation):
        """
        Receive a trade liquidation (not user trade, global).
        """
        pass

    def on_market_info(self):
        """
        When receive initial or update of market/instrument data.
        """
        pass

    #
    # watcher signals
    #

    def on_watcher_connected(self):
        """
        Watcher/broker connected.
        """
        pass

    def on_watcher_disconnected(self):
        """
        Watcher/broker lost connection.
        """
        pass

    #
    # balance signals
    #

    def on_account_balance(self, balance):
        """
        Receive a balance margin (free, available, percent...) update.
        """
        pass

    def on_asset_balance(self, balance):
        """
        Receive a balance update for a specific asset (free, locked, total) update.
        """
        pass

    #
    # region management
    #

    @property
    def regions(self):
        return self._regions

    def add_region(self, region):
        with self._mutex:
            region.set_id(self._next_region_id)
            self._next_region_id += 1
            self._regions.append(region)

    def remove_region(self, region_id):
        with self._mutex:
            for region in self._regions:
                if region.id == region_id:
                    self._regions.remove(region)
                    return True

        return False

    def cleanup_regions(self, timestamp, bid, ask):
        """
        Regenerate the list of regions by removing the expired regions.
        @warning Non thread-safe but must be protected.
        """
        regions = []

        for region in self._regions:
            if not region.can_delete(timestamp, bid, ask):
                regions.append(region)

        # replace the regions list
        self._regions = regions

    def check_regions(self, timestamp, bid, ask, signal, allow=True):
        """
        Compare a signal to defined regions if somes are defineds.
        @param signal StrategySignal to check with any regions.
        @param bid float Last instrument bid price
        @param ask float Last instrument ask price
        @param allow Default returned value if there is no defined region (default True).

        @note Thread-safe method.
        """
        if self._regions:
            mutated = False

            # one ore many region, have to pass at least one test
            with self._mutex:
                for region in self._regions:
                    if region.can_delete(timestamp, bid, ask):
                        mutated |= True

                    elif region.test_region(timestamp, signal):
                        # match with at least one region
                        return True

                if mutated:
                    self.cleanup_regions(timestamp, bid, ask)

            return False
        else:
            # no region always pass
            return allow

    #
    # alert management
    #

    @property
    def alerts(self):
        return self._alerts

    def add_alert(self, alert):
        with self._mutex:
            alert.set_id(self._next_alert_id)
            self._next_alert_id += 1
            self._alerts.append(alert)

    def remove_alert(self, alert_id):
        with self._mutex:
            for alert in self._alerts:
                if alert.id == alert_id:
                    self._alerts.remove(alert)
                    return True

        return False

    def cleanup_alerts(self, timestamp, bid, ask):
        """
        Regenerate the list of alerts by removing the expired alerts.
        @warning Non thread-safe but must be protected.
        """
        alerts = []

        for alert in self._alerts:
            if not alert.can_delete(timestamp, bid, ask):
                alerts.append(alert)

        # replace the alerts list
        self._alerts = alerts

    def check_alerts(self, timestamp, bid, ask, timeframes):
        """
        Compare timeframes indicators values to defined alerts if somes are defined.
        @param bid float Last instrument bid price
        @param ask float Last instrument ask price
        @param timeframes list of TimeframeBasedSub to check with any alerts.

        @note Thread-safe method.
        @note If the alert is triggered, it still keep alive until the next check_alerts call, even if its a one shot alert.
        """
        if self._alerts:
            mutated = False

            # one ore many alert, have to pass at least one test
            with self._mutex:
                results = []

                for alert in self._alerts:
                    if alert.can_delete(timestamp, bid, ask):
                        mutated |= True
                    else:
                        result = alert.test_alert(timestamp, bid, ask, timeframes)
                        if result:
                            # alert triggered, dump message could be done with alert dump_notify and result data
                            results.append((alert, result))

                if mutated:
                    self.cleanup_alerts(timestamp, bid, ask)

                if results:
                    return results

            return None
        else:
            # no alerts
            return None

    #
    # miscs
    #

    def update_trailing_stop(self, trade, instrument, distance, local=True, distance_in_percent=True):
        """
        Update the stop price of a trade using a simple level distance or percent distance method.
        @param local boolean True mean only modify the stop-loss price on this side,
            not on the position or on the stop order

        @note This method is not a way to process a stop, it mostly failed, close for nothing at a wrong price.
        """
        close_exec_price = instrument.close_exec_price(trade.direction)
        stop_loss = trade.sl

        if trade.direction > 0:
            # long case
            ratio = close_exec_price / trade.entry_price
            sl_ratio = (trade.entry_price - trade.sl) / trade.entry_price
            dist = (close_exec_price - trade.sl) / trade.entry_price
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
            # #     stop_loss = max(trade.sl, close_exec_price - (close_exec_price/trade.entry_price*(close_exec_price-trade.entry_price)*0.33))

            # # ultra large and based on the distance of the price
            # # if dist > 0.25:
            # #     stop_loss = trade.entry_price + (trade.entry_price * (dist * 0.5))

        elif trade.direction < 0:
            # short case
            ratio = close_exec_price / trade.entry_price
            sl_ratio = (trade.sl - trade.entry_price) / trade.entry_price
            dist = (trade.sl - close_exec_price) / trade.entry_price
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
                trade.modify_stop_loss(trader, instrument, stop_loss)

    def check_entry_canceled(self, trade):
        """
        Cancel entry if take-profit price is reached before filling the entry.
        """
        if trade.is_opened() and trade.tp > 0.0:
            if trade.direction > 0:
                if self.instrument.close_exec_price(trade.direction) >= trade.tp:
                    trader = self.strategy.trader()
                    trade.cancel_open(trader, self.instrument)
                    trade.exit_reason = trade.REASON_CANCELED_TARGETED
            elif trade.direction < 0:
                if self.instrument.close_exec_price(trade.direction) <= trade.tp:
                    trader = self.strategy.trader()
                    trade.cancel_open(trader, self.instrument)
                    trade.exit_reason = trade.REASON_CANCELED_TARGETED

            return True

        return False

    def check_entry_timeout(self, trade, timestamp, timeout):
        """
        Timeout then can cancel a non filled trade if exit signal occurs before timeout (timeframe).
        """
        if trade.is_entry_timeout(timestamp, timeout):
            trader = self.strategy.trader()
            trade.cancel_open(trader, self.instrument)
            trade.exit_reason = trade.REASON_CANCELED_TIMEOUT

            return True

        return False

    def check_trade_timeout(self, trade, timestamp):
        """
        Close a profitable trade that has passed its expiry.
        """
        if not trade:
            return False

        trade_profit_loss = trade.profit_loss

        if trade_profit_loss >= 0.0:
            if trade.context and trade.context.take_profit and trade.context.take_profit.timeout > 0 and trade.context.take_profit.timeout_distance != 0.0:
                if trade.is_duration_timeout(timestamp, trade.context.take_profit.timeout) and trade_profit_loss < trade.context.take_profit.timeout_distance:
                    trader = self.strategy.trader()
                    trade.close(trader, self.instrument)
                    trade.exit_reason = trade.REASON_MARKET_TIMEOUT

                    return True

        elif trade_profit_loss < 0.0:
            if trade.context and trade.context.stop_loss and trade.context.stop_loss.timeout > 0 and trade.context.stop_loss.timeout_distance != 0.0:
                if trade.is_duration_timeout(timestamp, trade.context.stop_loss.timeout) and -trade_profit_loss > trade.context.stop_loss.timeout_distance:
                    trader = self.strategy.trader()
                    trade.close(trader, self.instrument)
                    trade.exit_reason = trade.REASON_MARKET_TIMEOUT

                    return True

        return False

    def adjust_entry(self, trade, timeout):
        # if trade.is_opened() and not trade.is_valid(timestamp, trade.timeframe):
        #     # @todo re-adjust entry or cancel
        #     Terminal.inst().info("Update order %s trade %s TODO" % (trade.id, self.instrument.market_id,), view='default')
        #     continue

        return False

    def retrieve_context(self, name):
        """
        Return a trade context object. Used by set_trade_context.
        Must be overrided.
        """
        return None

    def apply_trade_context(self, trade, context):
        """
        Apply a trade context to a valide trade.
        Must be overrided.
        """
        if not trade or not context:
            return False

        return True

    def set_trade_context(self, trade, name):
        """
        Apply a trade context to a valide trade.
        Must be overrided.
        """
        if not trade or not name:
            return False

        context = self.retrieve_context(name)

        if not context:
            return False

        return self.apply_trade_context(trade, context)

    def contexts_ids(self):
        """
        Returns the list of context ids.
        Must be overrided.
        """
        return []

    def dumps_context(self, context_id):
        """
        Returns a dict with the normalized contexts details or None if don't exists.
        Must be overrided.
        """
        return None

    #
    # signal data streaming and monitoring
    #

    def create_chart_streamer(self, timeframe):
        """
        Create a streamer for the chart at a specific timeframe.
        Must be overrided.
        """
        return None

    def subscribe_stream(self, timeframe):
        """
        Use or create a specific streamer.
        Must be overrided.
        """
        return False

    def unsubscribe_stream(self, timeframe):
        """
        Delete a specific streamer when no more subscribers.
        Must be overrided.
        """
        return False

    def report_state(self, mode=0):
        """
        Collect the state of the strategy trader (instant) and return a dataset.
        Default only return a basic dataset, it must be overrided per strategy.

        @param mode integer Additional report context.
        """
        return {
            'market-id': self.instrument.market_id,
            'activity': self._activity,
            'affinity': self._affinity,
            'bootstraping': self._bootstraping == 2,
            'preprocessing': self._preprocessing == 2,
            'ready': self.instrument.ready(),
            'members': [],
            'data': [],
            'num-modes': 1
        }

    #
    # reporting
    #

    def report_path(self, *relative_path):
        """
        Check and generated a path where to write reporting files.
        """
        report_path = pathlib.Path(self.strategy.service.report_path)
        if report_path.exists():
            # only create the relative path (not the report if not exists, it might from config setup else its an issue)
            report_path = report_path.joinpath(*relative_path)
            if not report_path.exists():
                try:
                    report_path.mkdir(parents=True)
                except Exception as e:
                    error_logger(repr(e))
                    return None

                return report_path
            else:
                return report_path
        else:
            return None

    def default_report_filename(self, ext=".csv", header=None):
        """
        Generate a default filename for reporting.
        """
        report_path = self.report_path(self.strategy.identifier, self.instrument.market_id)
        if report_path:
            filename = str(report_path.joinpath(datetime.now().strftime('%Y%m%d_%Hh%Mm%S') + ext))

            try:
                f = open(filename, "wt")

                if header:
                    f.write(f + '\n')

                f.close()
            except Exception as e:
                error_logger.error(repr(e))
                return None

            return filename

        return None

    def write_report_row(self, row):
        """
        Write a new row into the report file. Default behavior.
        """
        if self._report_filename:
            try:
                f = open(self._report_filename, "at")
                f.write(",".join([str(v) for v in row]) + "\n")
            except Exception as e:
                error_logger.error(repr(e))
            finally:
                f.close()

    def report(self, trade, is_entry):
        """
        Override this method to write trade entry (when is_entry is True) and exit.
        """
        pass

    def report_header(self):
        """
        Override this method to write a header line into the report.
        """
        pass

    #
    # checks
    #

    def compute_asset_quantity(self, trader, price, trade_quantity=0.0):
        quantity = 0.0

        if not trade_quantity:
            # if not specified use default
            trade_quantity = self.instrument.trade_quantity

        if trader.has_asset(self.instrument.quote):
            # quantity = min(quantity, trader.asset(self.instrument.quote).free) / self.instrument.market_ask
            if trader.has_quantity(self.instrument.quote, trade_quantity or self.instrument.trade_quantity):
                quantity = self.instrument.adjust_quantity(trade_quantity / price)  # and adjusted to 0/max/step
            else:
                msg = "Not enought free quote asset %s, has %s but need %s" % (
                    self.instrument.quote,
                    self.instrument.format_quantity(trader.asset(self.instrument.quote).free),
                    self.instrument.format_quantity(trade_quantity))

                logger.warning(msg)
                Terminal.inst().notice(msg, view='status')
        else:
            msg = "Quote asset %s not found" % self.instrument.quote

            logger.warning(msg)
            Terminal.inst().notice(msg, view='status')

        return quantity

    def compute_margin_quantity(self, trader, price, trade_quantity=0.0):
        quantity = 0.0

        if not trade_quantity:
            # if not specified use default
            trade_quantity = self.instrument.trade_quantity

        original_quantity = trade_quantity

        if self.instrument.trade_quantity_mode == Instrument.TRADE_QUANTITY_QUOTE_TO_BASE:
            trade_quantity = self.instrument.adjust_quantity(trade_quantity / price)  # and adjusted to 0/max/step
        else:
            trade_quantity = self.instrument.adjust_quantity(trade_quantity)

        if trader.has_margin(self.instrument.market_id, trade_quantity, price):
            quantity = trade_quantity
        else:
            msg = "Not enought free margin %s, has %s but need %s" % (
                self.instrument.quote, self.instrument.format_quantity(trader.account.margin_balance),
                self.instrument.format_quantity(original_quantity))

            logger.warning(msg)
            Terminal.inst().notice(msg, view='status')

        return quantity

    def check_min_notional(self, order_quantity, order_price):
        if order_quantity <= 0 or order_quantity * order_price < self.instrument.min_notional:
            # min notional not reached
            msg = "Min notional not reached for %s, order %s%s => %s%s but need %s%s" % (
                    self.instrument.symbol,
                    order_quantity, self.instrument.base,
                    order_quantity * order_price, self.instrument.quote,
                    self.instrument.min_notional, self.instrument.quote)

            logger.warning(msg)
            Terminal.inst().notice(msg, view='status')

            return False

        return True

    def has_max_trades(self, max_trades, same_timeframe=0, same_timeframe_num=0):
        """
        @param max_trades Max simultaneous trades for this instrument.
        @param same_timeframe Compared timeframe.
        @param same_timeframe_num 0 mean Allow multiple trade of the same timeframe, else it define the max allowed.
        """
        result = False

        if self._trades:
            with self._trade_mutex:
                if len(self._trades) >= max_trades:
                    # no more than max simultaneous trades
                    result = True

                elif same_timeframe > 0 and same_timeframe_num > 0:
                    for trade in self._trades:
                        if trade.timeframe == same_timeframe:
                            same_timeframe_num -= 1
                            if same_timeframe_num <= 0:
                                result = True
                                break

        if result:
            msg = "Max trade reached for %s with %s or max reached for the timeframe" % (self.instrument.symbol, max_trades)

            # logger.warning(msg)
            Terminal.inst().notice(msg, view='status')

        return result

    #
    # notification
    #

    def notify_signal(self, timestamp, signal):
        if signal:
            # system notification
            self.strategy.notify_signal(timestamp, signal, self)

            # stream
            if self._signal_streamer:
                try:
                    self._signal_streamer.member('signal').update(self, signal, timestamp)
                    self._signal_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))

    def notify_trade_entry(self, timestamp, trade):
        if trade:
            # system notification
            self.strategy.notify_trade_entry(timestamp, trade, self)

            # stream
            if self._trade_entry_streamer:
                try:
                    self._trade_entry_streamer.member('trade-entry').update(self, trade, timestamp)
                    self._trade_entry_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))

            # for reporting if specified
            if self._reporting == self.REPORTING_VERBOSE:
                self.report(trade, True)

    def notify_trade_update(self, timestamp, trade):
        if trade:
            # stream only but could be remove, client will update using tickers, and only receive amends update
            if self._trade_update_streamer:
                try:
                    self._trade_update_streamer.member('trade-update').update(self, trade, timestamp)
                    self._trade_update_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))

    def notify_trade_exit(self, timestamp, trade):
        if trade:
            # system notification
            self.strategy.notify_trade_exit(timestamp, trade, self)

            # stream
            if self._trade_exit_streamer:
                try:
                    self._trade_exit_streamer.member('trade-exit').update(self, trade, timestamp)
                    self._trade_exit_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))

            # for reporting if specified
            if self._reporting == self.REPORTING_VERBOSE:
                self.report(trade, False)

    def notify_alert(self, timestamp, alert, result):
        if alert and result:
            # system notification
            self.strategy.notify_alert(timestamp, alert, result, self)

            # stream
            if self._alert_streamer:
                try:
                    self._alert_streamer.member('alert').update(self, alert, result, timestamp)
                    self._alert_streamer.publish()
                except Exception as e:
                    logger.error(repr(e))
