# @date 2018-09-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Generic paper trader.

import json
import time
import copy
import base64
import uuid

from datetime import datetime

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from trader.trader import Trader

from .account import PaperTraderAccount
from trader.position import Position
from trader.order import Order
from trader.asset import Asset
from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.trader.papertrader')


class PaperTraderHistoryEntry(object):
    """
    History entry when paper trading, but could be done by an external listener, eventually a webapp.
    @todo Report the duration of the trade.
    @todo Streamable and for any trader, and more uniform.
    """

    def __init__(self, order, balance, margin_balance, gain_loss_pip=None, gain_loss_rate=None, gain_loss_currency=None, gain_loss_account_currency=None):
        self._uid = 0
        self._order = order
        self._balance = balance
        self._margin_balance = margin_balance
        # self._asset_balance = asset_balance

        self._gain_loss_pip = gain_loss_pip
        self._gain_loss_rate = gain_loss_rate
        self._gain_loss_currency = gain_loss_currency
        self._gain_loss_account_currency = gain_loss_account_currency

    def set_uid(self, uid):
        self._uid = uid

    @property
    def order(self):
        return self._order
    
    @property
    def balance(self):
        return self._balance

    @property
    def margin_balance(self):
        return self._margin_balance

    @property
    def gain_loss_pip(self):
        return self._gain_loss_pip

    @property
    def gain_loss_rate(self):
        return self._gain_loss_rate

    @property
    def gain_loss_currency(self):
        return self._gain_loss_currency

    @property
    def gain_loss_account_currency(self):
        return self._gain_loss_account_currency

    def report(self, currency):
        """
        Return a string report.
        """
        direction = "LONG" if self._order.direction == Position.LONG else "SHORT"
        at = datetime.fromtimestamp(self._order.transact_time).strftime('%Y-%m-%dT%H:%M:%S.%fZ') if self._order.transact_time else ""

        if self._gain_loss_pip is not None:
            return '\t'.join((str(self._uid), "EXIT", direction, self._order.symbol, str(self._order.quantity), at,
                str(self._gain_loss_pip), str(self._gain_loss_rate*100.0), str(self._gain_loss_currency), str(self._balance)))
        else:
            return '\t'.join((str(self._uid), "ENTER", direction, self._order.symbol, str(self._order.quantity), at, "0", "0", "0", str(self._balance)))


class PaperTraderHistory(object):
    """
    History when paper trading, but could be done by an external listener, eventually a webapp.
    @todo margin_balance issue again !
    @todo generate/call signal for order and position (create, update, delete, reject, cancel) but how to manage them because if strategy listen from watcher ?
    @todo distinct multiple position of single per instrument and hedging mode.
    @todo add signals emit for position opened/update/closed
    @todo execution of limit order on price not as now as market with limit price (but for now it works because of the strategy ask for the ofr price and small volume)
    @todo with limit order lock the qty of the asset
    @todo check available margin when creating margin order
    @todo Best/worst are made for margin on account currency, but need to be updated to work with asset
    """

    def __init__(self, trader):
        self._trader = trader
        self._history = []

        self._live_rate = {}  # live rate in percent per market
        self._create_time = datetime.now()

    def add(self, entry):
        if entry:
            self._history.append(entry)
            entry.set_uid(len(self._history))

            if entry.order.symbol not in self._live_rate:
                self._live_rate[entry.order.symbol] = [0, 0]

            if entry.gain_loss_rate:
                self._live_rate[entry.order.symbol][0] += entry.gain_loss_rate
                self._live_rate[entry.order.symbol][1] += entry.gain_loss_currency

    def log_report(self):
        """
        Report to a log file into the report path.
        """
        currency = self._trader.account.currency

        # stats, and write
        worst_loss = 0
        best_profit = 0

        winners = 0
        loosers = 0
        equities = 0

        best_serie = 0
        worst_serie = 0

        prev_gp = 0

        count_best = 0
        count_worst = 0

        # chart data
        arr_balances = []
        arr_gain_loss_pips = []
        arr_gain_loss_currency = []
        arr_gain_loss_currency_name = []
        arr_gain_loss_account_currency = []
        arr_gain_loss_rates = []

        #
        # log trades as tab separated format
        #

        log_name = "%s_%s_trades.log" % (self._create_time.strftime('%Y%m%dT%H-%M-%S'), self._trader.name)
        log_o = open(self._trader.service.report_path + "/" + log_name, "wt")

        # header
        log_o.write('\t'.join(('ID', 'TYPE', 'DIRECTION', 'MARKET', 'QUANTITY', 'TRANSACT', 'PL_PIP', 'PL_PERCENT', 'PL_CURRENCY', 'BALANCE')) + '\n')

        pc_sum = 0
        for entry in self._history:
            arr_balances.append(entry.balance)

            arr_gain_loss_pips.append(entry.gain_loss_pip)
            arr_gain_loss_currency.append(entry.gain_loss_currency)
            arr_gain_loss_rates.append(entry.gain_loss_rate)
            arr_gain_loss_currency_name.append(entry.order.symbol)
            arr_gain_loss_account_currency.append(entry.gain_loss_account_currency)

            if entry.gain_loss_pip is not None:
                pc_sum += entry.gain_loss_rate

                worst_loss = min(worst_loss, entry.gain_loss_account_currency)
                best_profit = max(best_profit, entry.gain_loss_account_currency)

                if entry.gain_loss_pip > 0:
                    winners += 1
                    
                    if prev_gp > 0:
                        count_best += 1
                        count_worst = 1
                    
                    prev_gp = +1

                elif entry.gain_loss_pip < 0:
                    loosers += 1

                    if prev_gp < 0:
                        count_worst += 1
                        count_best = 1

                    prev_gp = -1

                else:
                    equities += 1
                    prev_gp = 0

                best_serie = max(best_serie, count_best)
                worst_serie = max(worst_serie, count_worst)

                prev_gp = entry.gain_loss_pip

            log_o.write(entry.report(currency) + '\n')

        log_o.close()
        log_o = None

        #
        # log report
        #

        # conversion in account currency are done at the same market price, so its very approximative
        log_name = "%s_%s_report.log" % (self._create_time.strftime('%Y%m%dT%H-%M-%S'), self._trader.name)
        log_o = open(self._trader.service.report_path + "/" + log_name, "wt")

        log_o.write("# Note that conversion in account currency are done at the same market price, so its very approximative.\n")
        log_o.write("- Total %.2f%% with %s trades\n" % (pc_sum, len(self._history)))
        log_o.write("- Best profit %.2f%s / Worst loss %.2f%s\n" % (best_profit, currency, worst_loss, currency))
        log_o.write("- Winners %s / Loosers %s / Equities %s\n" % (winners, loosers, equities))
        log_o.write("- Best serie len %s / Worst serie len %s\n" % (best_serie, worst_serie))

        log_o.close()
        log_o = None

        #
        # log py data (useful to chart them)
        #

        log_name = "%s_%s_data.py" % (self._create_time.strftime('%Y%m%dT%H-%M-%S'), self._trader.name)
        log_o = open(self._trader.service.report_path + "/" + log_name, "wt")

        log_o.write("balances = %s\n\n" % repr(arr_balances))
        log_o.write("profit_loss_pips = %s\n\n" % repr(arr_gain_loss_pips))
        log_o.write("profit_loss_currency = %s\n\n" % repr(arr_gain_loss_currency))
        log_o.write("profit_loss_rates = %s\n\n" % repr(arr_gain_loss_rates))
        log_o.write("profit_loss_currency_name = %s\n\n" % repr(arr_gain_loss_currency_name))
        log_o.write("profit_loss_account_currency = %s\n\n" % repr(arr_gain_loss_account_currency))

        log_o.close()
        log_o = None

    def get_live_report(self):
        """
        Returns live performance in an array. 
        """
        results = []

        for k, rate in self._live_rate.items():
            results.append((k, rate[0], rate[1]))

        return results


class PaperTrader(Trader):
    """
    Only for simulation paper trader.
    In backtesting market data are set manually using method set_market(...).

    @todo support of slippage will need a list of order, and to process in update time, and need a tick level or order book data.
    @note ORDER_STOP_LIMIT and ORDER_TAKE_PROFIT_LIMIT orders are not implemented at this time
    @todo A profil with unlimited asset/margin.
    @issue Margin computation with BitMex markets (base exchange rate or what else is going wrong during the calculation ?)
    """

    def __init__(self, service, name="papertrader.siis"):
        super().__init__(name, service)

        self._spreads = {}  # spread per market
        self._slippage = 0  # slippage in ticks (not supported for now)

        self._watcher = None  # in backtesting refers to a dummy watcher

        self._history = PaperTraderHistory(self)  # trades history for reporting
        self._account = PaperTraderAccount(self)

        self._ordering = []  # pending list of orders operation (create, cancel, modify)

    @property
    def paper_mode(self):
        return True

    @property
    def authenticated(self):
        # always authenticated in paper-mode
        return True

    @property
    def connected(self):
        if self.service.backtesting:
            # always connected in backtesting
            return True
        else:
            return self._watcher is not None and self._watcher.connector is not None and self._watcher.connector.connected

    def connect(self):
        super().connect()

        if self.service.backtesting:
            # no connection when backtesting
            return

        # retrieve the pair watcher and take its connector
        self.lock()

        self._watcher = self.service.watcher_service.watcher(self._name)

        if self._watcher:
            self.service.watcher_service.add_listener(self)

        self.unlock()

        if self._watcher and self._watcher.connected:
            self.on_watcher_connected(self._watcher.name)   

    def disconnect(self):
        super().disconnect()

        self.lock()

        if self._watcher:
            self.service.watcher_service.remove_listener(self)
            self._watcher = None

        self.unlock()

    def on_watcher_connected(self, watcher_name):
        super().on_watcher_connected(watcher_name)

        logger.info("Paper trader %s retrieving symbols and markets..." % self._name)

        # fetch tradable markets
        configured_symbols = self.configured_symbols()
        matching_symbols = self.matching_symbols_set(configured_symbols, self._watcher.watched_instruments())

        # only configured symbols found in watched symbols
        for symbol in matching_symbols:
            self.market(symbol, True)

        # insert the assets
        # @todo

        logger.info("Paper trader %s data symbols and markets retrieved." % self._name)

    def on_watcher_disconnected(self, watcher_name):
        super().on_watcher_disconnected(watcher_name)

    def has_margin(self, margin):
        """
        Return True for a margin trading if the account have suffisient free margin.
        @note The benefit of this method is it can be overloaded and offers a generic way for a strategy
            to check if an order can be created
        """
        return self.account.margin_balance >= margin

    def has_quantity(self, asset_name, quantity):
        """
        Return True if a given asset has a minimum quantity.
        @note The benefit of this method is it can be overloaded and offers a generic way for a strategy
            to check if an order can be created
        """
        result = False

        self.lock()
        asset = self._assets.get(asset_name)
        result = asset and asset.free >= quantity
        self.unlock()

        return result

    def market(self, market_id, force=False):
        """
        Fetch from the watcher and cache it. It rarely changes so assume it once per connection.
        @param force Force to update the cache
        """
        market = self._markets.get(market_id)

        if (market is None or force) and self._watcher is not None and self._watcher.connected:
            try:
                market = self._watcher.fetch_market(market_id)
            except Exception as e:
                logger.error("fetch_market: %s" % repr(e))
                return None

            if market:
                self._markets[market_id] = market

        return market

    def post_update(self):
        super().post_update()

        # don't wast the CPU 5 ms loop, and this will simulate at least a 5ms slippage for limits order execution in paper-mode
        if not self.service.backtesting:
            time.sleep(0.0001)
        time.sleep(0.005)

    def log_report(self):
        self._history.log_report()

    @property
    def timestamp(self):
        """
        Current real time or last timestamp in backtesting
        """
        if self.service.backtesting:
            return self._timestamp
        else:
            return time.time()

    def update(self):
        """
        This update its called synchronously by appliance update during the backtesting or threaded in live mode.
        """
        super().update()

        #
        # update positions (margin trading)
        #

        if self._positions:
            rm_list = []

            self.lock()

            for k, position in self._positions.items():
                # simulate liquidation of positions
                # @todo but its complex

                # remove empty and closed positions
                if position.quantity <= 0.0:
                    rm_list.append(k)
                else:
                    market = self._markets.get(position.symbol)
                    if market:
                        # update profit/loss of each position
                        position.update_profit_loss(market)

            for rm in rm_list:
                # remove empty positions
                del self._positions[rm]

            self.unlock()

        #
        # update account balance and margin
        #

        self.lock()
        self._account.update(None)
        self.unlock()

        if self._account.account_type & PaperTraderAccount.TYPE_MARGIN:
            # support margin
            used_margin = 0
            profit_loss = 0

            self.lock()

            for k, position in self._positions.items():
                market = self._markets.get(position.symbol)
                
                # only for non empty positions
                if market and position.quantity > 0.0:
                    # manually compute here because of paper trader
                    profit_loss += position.profit_loss_market / market.base_exchange_rate
                    used_margin += position.margin_cost(market) / market.base_exchange_rate

            self.unlock()

            self.account.set_used_margin(used_margin+profit_loss)
            self.account.set_unrealized_profit_loss(profit_loss)

        if self._account.account_type & PaperTraderAccount.TYPE_ASSET:
            # support spot
            balance = 0.0
            free_balance = 0.0
            profit_loss = 0.0

            self.lock()

            for k, asset in self._assets.items():
                asset_name = asset.symbol
                free = asset.free
                locked = asset.locked

                if free or locked:
                    # asset price in quote
                    if asset_name == self._account.alt_currency:
                        # asset second currency
                        market = self._markets.get(self._account.currency+self._account.alt_currency)
                        base_price = 1.0 / market.price if market else 1.0
                    elif asset_name != self._account.currency:
                        # any asset except asscount currency
                        market = self._markets.get(asset_name+self._account.currency)
                        base_price = market.price if market else 1.0
                    else:
                        # asset account currency itself
                        base_price = 1.0

                    if asset.quote == self._account.alt_currency:
                        # change from alt currency to primary currency
                        market = self._markets.get(self._account.currency+self._account.alt_currency)
                        base_exchange_rate = market.price if market else 1.0
                    elif asset.quote == self._account.currency:
                        # asset is account currency not change
                        base_exchange_rate = 1.0
                    else:
                        # change from quote to primary currency
                        market = self._markets.get(asset.quote+self._account.currency)
                        base_exchange_rate = 1.0 / market.price if market else 1.0

                    balance += free * base_price + locked * base_price  # current total free+locked balance
                    free_balance += free * base_price                   # current total free balance

                    # current profit/loss at market
                    profit_loss += asset.profit_loss_market / base_exchange_rate  # current total P/L in primary account currency

            self.account.set_asset_balance(balance, free_balance)
            self.account.set_unrealized_asset_profit_loss(profit_loss)

            self.unlock()

        #
        # limit/trigger orders executions
        #
        if self._orders:
            rm_list = []

            self.lock()
            orders = list(self._orders.values())
            self.unlock()

            for order in orders:
                market = self._markets.get(order.symbol)
                if market is None:
                    # unsupported market
                    rm_list.append(order.order_id)
                    continue

                # slippage emulation
                # @todo deferred execution, could make a rand delay around the slippage factor

                # open long are executed on bid and short on ofr, close the inverse
                if order.direction == Position.LONG:
                    open_exec_price = market.ofr
                    close_exec_price = market.bid
                elif order.direction == Position.SHORT:
                    open_exec_price = market.bid
                    close_exec_price = market.ofr
                else:
                    # unsupported direction
                    rm_list.append(order.order_id)
                    continue

                if order.order_type == Order.ORDER_MARKET:
                    # market
                    # does not support the really offered qty, take all at current price in one shot
                    if order.margin_trade and market.has_margin:
                        if market.indivisible_position:
                            self.__exec_ind_margin_order(order, market, open_exec_price, close_exec_price)
                        else:
                            self.__exec_margin_order(order, market, open_exec_price, close_exec_price)
                    elif not order.margin_trade and market.has_spot:
                        self.__exec_buysell_order(order, market, open_exec_price, close_exec_price)

                    # fully executed
                    rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_LIMIT:
                    # limit
                    if ((order.direction == Position.LONG and open_exec_price <= order.price) or
                        (order.direction == Position.SHORT and open_exec_price >= order.price)):

                        # does not support the really offered qty, take all at current price in one shot
                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                self.__exec_ind_margin_order(order, market, open_exec_price, close_exec_price)
                            else:
                                self.__exec_margin_order(order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            self.__exec_buysell_order(order, market, open_exec_price, close_exec_price)

                        # fully executed
                        rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_STOP:
                    # trigger + market
                    if ((order.direction == Position.LONG and close_exec_price >= order.stop_price) or
                        (order.direction == Position.SHORT and close_exec_price <= order.stop_price)):

                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                self.__exec_ind_margin_order(order, market, open_exec_price, close_exec_price)
                            else:
                                self.__exec_margin_order(order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            self.__exec_buysell_order(order, market, open_exec_price, close_exec_price)

                        # fully executed
                        rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_STOP_LIMIT:
                    # trigger + limit
                    if ((order.direction == Position.LONG and close_exec_price >= order.stop_price) or
                        (order.direction == Position.SHORT and close_exec_price <= order.stop_price)):

                        # limit
                        if order.direction == Position.LONG:
                            open_exec_price = min(order.price, open_exec_price)
                            close_exec_price = min(order.price, close_exec_price)
                        elif order.direction == Position.SHORT:
                            open_exec_price = max(order.price, open_exec_price)
                            close_exec_price = max(order.price, close_exec_price)

                        # does not support the really offered qty, take all at current price in one shot
                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                self.__exec_ind_margin_order(order, market, open_exec_price, close_exec_price)
                            else:
                                self.__exec_margin_order(order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            self.__exec_buysell_order(order, market, open_exec_price, close_exec_price)

                    # fully executed
                    rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_TAKE_PROFIT:
                    # opposite trigger + market
                    if ((order.direction == Position.LONG and close_exec_price <= order.stop_price) or
                        (order.direction == Position.SHORT and close_exec_price >= order.stop_price)):

                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                self.__exec_ind_margin_order(order, market, open_exec_price, close_exec_price)
                            else:
                                self.__exec_margin_order(order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            self.__exec_buysell_order(order, market, open_exec_price, close_exec_price)

                    # fully executed
                    rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_TAKE_PROFIT_LIMIT:
                    # opposite trigger + limit
                    if ((order.direction == Position.LONG and close_exec_price <= order.stop_price) or
                        (order.direction == Position.SHORT and close_exec_price >= order.stop_price)):

                        # limit
                        if order.direction == Position.LONG:
                            open_exec_price = min(order.price, open_exec_price)
                            close_exec_price = min(order.price, close_exec_price)
                        elif order.direction == Position.SHORT:
                            open_exec_price = max(order.price, open_exec_price)
                            close_exec_price = max(order.price, close_exec_price)

                        # does not support the really offered qty, take all at current price in one shot
                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                self.__exec_ind_margin_order(order, market, open_exec_price, close_exec_price)
                            else:
                                self.__exec_margin_order(order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                                self.__exec_buysell_order(order, market, open_exec_price, close_exec_price)

                    # fully executed
                    rm_list.append(order.order_id)

            self.lock()

            for rm in rm_list:
                # remove fully executed orders
                if rm in self._orders:
                    del self._orders[rm]

            self.unlock()

    def create_asset(self, asset_name, quantity, price, quote, precision=8):
        asset = Asset(self, asset_name, precision)
        asset.set_quantity(0, quantity)
        asset.update_price(datetime.now(), 0, price, quote)

        self.lock()
        self._assets[asset_name] = asset
        self.unlock()

    def create_order(self, order):
        if order is None:
            return False

        if not self._activity:
            return False

        if not self.has_market(order.symbol):
            logger.error("Trader %s does not support market %s in ref order %s !" % (self.name, order.symbol, order.ref_order_id))
            return False

        market = self.market(order.symbol)

        if (market.min_size > 0.0) and (order.quantity < market.min_size):
            # reject if lesser than min size
            logger.error("Trader %s refuse order because the min size is not reached (%.f<%.f) %s in ref order %s" % (
                self.name, order.quantity, market.min_size, order.symbol, order.ref_order_id))
            return False

        #
        # price according to order type
        #

        bid_price = 0
        ofr_price = 0

        if order.order_type in (Order.ORDER_LIMIT, Order.ORDER_STOP_LIMIT, Order.ORDER_TAKE_PROFIT_LIMIT):
            bid_price = order.price
            ofr_price = order.price

        elif order.order_type in (Order.ORDER_MARKET, Order.ORDER_STOP, Order.ORDER_TAKE_PROFIT):
            bid_price = market.bid
            ofr_price = market.ofr

        # open long are executed on bid and short on ofr, close the inverse
        if order.direction == Position.LONG:
            open_exec_price = ofr_price
            close_exec_price = bid_price
        elif order.direction == Position.SHORT:
            open_exec_price = bid_price
            close_exec_price = ofr_price
        else:
            logger.error("Unsupported direction")
            return False

        if not open_exec_price or not close_exec_price:
            logger.error("No order execution price")
            return False

        # adjust quantity to step min and max, and round to decimal place of min size, and convert it to str
        quantity = order.quantity  # market.adjust_quantity(order.quantity)
        notional = quantity * open_exec_price

        if notional < market.min_notional:
            # reject if lesser than min notinal
            logger.error("%s refuse order because the min notional is not reached (%.f<%.f) %s in ref order %s" % (
                self.name, notional, market.min_notional, order.symbol, order.ref_order_id))
            return False

        # unique order id
        order_id =  "siis_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n')
        order.set_order_id(order_id)
        order.created_time = self.timestamp

        if order.order_type == Order.ORDER_MARKET:
            # immediate execution of the order at market
            # @todo or add to orders for emulate the slippage

            if order.margin_trade and market.has_margin:
                if market.indivisible_position:
                    return self.__exec_ind_margin_order(order, market, open_exec_price, close_exec_price)
                else:
                    return self.__exec_margin_order(order, market, open_exec_price, close_exec_price)
            elif not order.margin_trade and market.has_spot:
                return self.__exec_buysell_order(order, market, open_exec_price, close_exec_price)
        else:
            # create accepted, add to orders
            self.lock()
            self._orders[order_id] = order
            self.unlock()

            #
            # order signal
            #

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'direction': order.direction,
                'timestamp': order.created_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force
            }

            # signal as watcher service (opened + full traded qty and immediately deleted)
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (order.symbol, order_data, order.ref_order_id))

            return True

        return False

    def post_run(self):
        super().post_run()

    def cancel_order(self, order_id):
        if not self._activity:
            return False

        result = False

        order_symbol = ""

        self.lock()

        order = self._orders.get(order_id)
        if order:
            order_symbol = order.symbol
            del self._orders[order_id]
            order = None
            result = True

        self.unlock()

        if result:
            # signal of canceled order
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_CANCELED, self.name, (order_symbol, order_id, ""))

        return result

    def close_position(self, position_id, market=True, limit_price=None):
        if not self._activity:
            return False

        result = False

        self.lock()
        position = self._positions.get(position_id)

        if position and position.is_opened():
            # market stop order
            order = Order(self, position.symbol)
            order.set_position_id(position_id)

            order.direction = position.close_direction()

            if market and limit_price:
                order.order_type = Order.ORDER_LIMIT
                order.price = limit_price
            else:
                order.order_type = Order.ORDER_MARKET

            order.quantity = position.quantity  # fully close
            order.leverage = position.leverage  # same as open

            order.close_only = True
            order.reduce_only = True

            self.unlock()

            #
            # price according to order type
            #

            market = self.market(order.symbol)

            bid_price = 0
            ofr_price = 0

            if order.order_type == Order.ORDER_LIMIT:
                bid_price = order.price
                ofr_price = order.price

            elif order.order_type == Order.ORDER_MARKET:
                bid_price = market.bid
                ofr_price = market.ofr

            # open long are executed on bid and short on ofr, close the inverse
            if order.direction == Position.LONG:
                open_exec_price = ofr_price  # bid_price
                close_exec_price = bid_price  # ofr_price
            elif order.direction == Position.SHORT:
                open_exec_price = bid_price  # ofr_price
                close_exec_price = ofr_price  # bid_price
            else:
                logger.error("Unsupported direction")
                return False

            if not open_exec_price or not close_exec_price:
                logger.error("No order execution price")
                return False

            if self._slippage > 0.0:
                # @todo
                return False
            else:
                # immediate execution of the order
                result = self.__exec_margin_order(order, market, open_exec_price, close_exec_price)
        else:
            self.unlock()
            result = False         

        return result

    def modify_position(self, position_id, stop_loss_price=None, take_profit_price=None):
        if not self._activity:
            return False

        result = False
        self.lock()

        position = self._positions.get(position_id)
        if position and position.is_opened():
            position.stop_loss = stop_loss_price
            position.take_profit = take_profit_price
            result = True

        self.unlock()

        return result

    def positions(self, market_id):
        # possible hedging... filter by market id
        positions = []

        self.lock()
        for k, position in self._positions.items():
            if position.symbol == market_id:
                positions.append(copy.copy(position))
        self.unlock()

        return positions

    def set_market(self, market):
        """
        Set market info object. Used during backtesting.

        The paper trader can receive data from the real related watcher, but in case of
        backtesting there is not connexion made, then market data are simulated from the record in the database.
        Initial information must then be manually defined throught this methos.
        """
        if market:
            self.lock()
            self._markets[market.market_id] = market
            self.unlock()

    def on_account_updated(self, balance, free_margin, unrealized_pnl, currency, risk_limit):
        # not interested in account details
        pass

    def on_position_opened(self, market_id, position_data, ref_order_id):
        # not interested in account positions
        pass

    def on_position_amended(self, market_id, position_data, ref_order_id):
        pass
        
    def on_position_updated(self, market_id, position_data, ref_order_id):
        pass

    def on_position_deleted(self, market_id, position_id, ref_order_id):
        pass

    def on_order_opened(self, market_id, order_data, ref_order_id):
        # not interested in account orders
        pass

    def on_order_updated(self, market_id, order_data, ref_order_id):
        pass

    def on_order_deleted(self, market_id, order_id, ref_order_id):
        pass

    def on_order_traded(self, market_id, order_data, ref_order_id):
        pass        

    def on_update_market(self, market_id, tradable, last_update_time, bid, ofr,
            base_exchange_rate, contract_size=None, value_per_pip=None,
            vol24h_base=None, vol24h_quote=None):

        super().on_update_market(market_id, tradable, last_update_time, bid, ofr, base_exchange_rate, contract_size, value_per_pip, vol24h_base, vol24h_quote)

        # update positions profit/loss for the related market id
        market = self.market(market_id)

        # market must be valid and currently tradeable
        if market is None:
            return

        self.lock()

        # update profit/loss (informational) for each asset
        for k, asset in self._assets.items():
            if asset.symbol == market.base and asset.quote == market.quote:
                asset.update_profit_loss(market)

        # update profit/loss for each positions
        for k, position in self._positions.items():
            if position.symbol == market.market_id:
                position.update_profit_loss(market)

        self.unlock()

    #
    # utils
    #

    def adjust_quantity(self, quantity, step_size=0.00000001, precision=8):
        return round(step_size * round(quantity / step_size), precision)

    def get_live_report(self):
        self.lock()
        results = self._history.get_live_report()
        self.unlock()

        return results

    #
    # protected
    #

    def __get_or_add_asset(self, asset_name, precision=8):
        if asset_name in self._assets:
            return self._assets[asset_name]

        asset = Asset(self, asset_name, precision)
        asset.quote = self._account.currency

        if self._watcher:
            if self._watcher.has_instrument(asset_name+self._account.currency):
                asset.quote = self._account.currency
            elif self._watcher.has_instrument(asset_name+self._account.alt_currency):
                asset.quote = self._account.alt_currency
        else:
            if self.has_market(asset_name+self._account.currency):
                asset.quote = self._account.currency
            elif self.has_market(asset_name+self._account.alt_currency):
                asset.quote = self._account.alt_currency

        for k, market in self._markets.items():
            if market.base == asset_name:
                asset.add_market_id(market.market_id)

        self._assets[asset_name] = asset

        return asset

    #
    # spot
    #

    def __exec_buysell_order(self, order, market, open_exec_price, close_exec_price):
        """
        Execute the order for buy&sell of asset.
        """
        result = False

        self.lock()

        base_asset = self.__get_or_add_asset(market.base)
        quote_asset = self.__get_or_add_asset(market.quote)

        quote_market = self._markets.get(quote_asset.symbol+quote_asset.quote)
        quote_exec_price = quote_market.price if quote_market else 1.0

        if order.direction == Position.LONG:
            # buy
            base_qty = order.quantity  # market.adjust_quantity(order.quantity)
            quote_qty = base_qty * open_exec_price  # quote_market.adjust_quantity(base_qty * open_exec_price) if quote_market else self.adjust_quantity(base_qty * open_exec_price)

            # @todo free quantity
            if quote_qty > quote_asset.quantity:
                self.unlock()

                # and then rejected order
                self.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, self.name, (order.symbol, order.ref_order_id))

                logger.error("Not enought quote asset quantity for %s with %s (have %s)!" % (quote_asset.symbol, quote_qty, quote_asset.quantity))
                return False

            # retain the fee on the quote asset
            commission_asset = quote_asset.symbol

            if order.is_market():
                commission_amount = quote_qty * market.taker_fee
            else:
                commission_amount = quote_qty * market.maker_fee

            quote_qty += commission_amount

            # base asset. it will receive its own signal (ignored)
            self.__update_asset(order.order_type, base_asset, market, 0, open_exec_price, base_qty, True, self.timestamp)
            # quote asset
            self.__update_asset(order.order_type, quote_asset, quote_market, 0, quote_exec_price, quote_qty, False, self.timestamp)

            # directly executed quantity
            order.executed = base_qty

            # transaction time is current timestamp
            order.transact_time = self.timestamp

            result = True

            #
            # history
            #

            # and keep for history (backtesting reporting)
            history = PaperTraderHistoryEntry(order, self.account.balance, self.account.margin_balance)
            self._history.add(history)

            # unlock before notify signals
            self.unlock()

            #
            # order signal
            #

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'direction': order.direction,
                'timestamp': order.created_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force
            }

            # signal as watcher service (opened + full traded qty and immediately deleted)
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (order.symbol, order_data, order.ref_order_id))

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'trade-id': 0,
                'direction': order.direction,
                'timestamp': order.transact_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'exec-price': open_exec_price,
                'filled': base_qty,
                'cumulative-filled': base_qty,
                'quote-transacted': quote_qty,
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force,
                'commission-amount': commission_amount,
                'commission-asset': commission_asset
            }

            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (order.symbol, order_data, order.ref_order_id))
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (order.symbol, order.order_id, ""))

        elif order.direction == Position.SHORT:
            # sell
            base_qty = order.quantity  # market.adjust_quantity(order.quantity)
            quote_qty = base_qty * close_exec_price  # quote_market.adjust_quantity(base_qty * close_exec_price) if quote_market else self.adjust_quantity(base_qty * close_exec_price)

            # @todo free quantity
            if base_qty > base_asset.quantity:
                self.unlock()

                # and then rejected order
                self.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, self.name, (order.symbol, order.ref_order_id))

                logger.error("Not enought base asset quantity for %s with %s (have %s)!" % (
                    base_asset.symbol, market.format_quantity(base_qty), market.format_quantity(base_asset.quantity)))

                return False

            # retain the fee from the quote asset
            commission_asset = quote_asset.symbol

            if order.is_market():
                commission_amount = quote_qty * market.taker_fee
            else:
                commission_amount = quote_qty * market.maker_fee

            quote_qty -= commission_amount

            # approximation of the profit/loss according to the average price of the base asset
            delta_price = close_exec_price - base_asset.price

            # it will receive its own signal (ignored)
            self.__update_asset(order.order_type, base_asset, market, 0, close_exec_price, base_qty, False, self.timestamp)
            # quote asset
            position_gain_loss_currency = self.__update_asset(order.order_type, quote_asset, quote_market, 0, quote_exec_price, quote_qty, True, self.timestamp)

            gain_loss_rate = ((close_exec_price - base_asset.price) / base_asset.price) if base_asset.price else 0.0
            position_gain_loss = delta_price * base_qty
            position_gain_loss_currency *= gain_loss_rate

            # directly executed quantity
            order.executed = base_qty

            # transaction time is current timestamp
            order.transact_time = self.timestamp

            result = True

            #
            # history
            #

            # and keep for history (backtesting reporting)
            history = PaperTraderHistoryEntry(order, self.account.balance, self.account.margin_balance, delta_price/market.one_pip_means,
                gain_loss_rate, position_gain_loss, position_gain_loss_currency)
            self._history.add(history)

            # unlock before notify signals
            self.unlock()

            #
            # order signal
            #

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'direction': order.direction,
                'timestamp': order.created_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force
            }

            # signal as watcher service (opened + fully traded qty and immediately deleted)
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (order.symbol, order_data, order.ref_order_id))

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'trade-id': 0,
                'direction': order.direction,
                'timestamp': order.transact_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'exec-price': close_exec_price,
                'filled': base_qty,
                'cumulative-filled': base_qty,
                'quote-transacted': quote_qty,
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force,
                'commission-amount': commission_amount,
                'commission-asset': commission_asset
            }

            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (order.symbol, order_data, order.ref_order_id))
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (order.symbol, order.order_id, ""))

        return result

    def __update_asset(self, order_type, asset, market, trade_id, exec_price, trade_qty, buy_or_sell, timestamp):
        """
        Update asset price and quantity.
        """
        curr_price = asset.price  # in asset prefered quote symbol
        curr_qty = asset.quantity

        # base price in quote, time in seconds
        quote_price = 1.0

        if market:
            if asset.symbol != self._account.currency and market.quote != self._account.currency:
                # asset is not quote, quote is not default, get its price at trade time
                if self._watcher:
                    if self._watcher.has_instrument(market.quote+self._account.currency):
                        # direct
                        quote_price = self.history_price(market.quote+self._account.currency, timestamp)  # REST call but cost API call and delay
                    elif self._watcher.has_instrument(self._account.currency+market.quote):
                        # indirect
                        quote_price = 1.0 / self.history_price(self._account.currency+market.quote, timestamp)  # REST call but cost API call and delay
                    else:
                        quote_price = 0.0  # might not occurs
                        logger.warning("Unsupported quote asset " + market.quote)
                else:
                    if self.has_market(market.quote+self._account.currency):
                        # direct
                        quote_price = self._markets[market.quote+self._account.currency].price
                    elif self.has_market(self._account.currency+market.quote):
                        # indirect
                        quote_price = 1.0 / self._markets[self._account.currency+market.quote].price
                    else:
                        quote_price = 0.0  # might not occurs
                        logger.warning("Unsupported quote asset " + market.quote)

            price = exec_price * quote_price

            # in quote
            if curr_qty+trade_qty > 0.0:
                if buy_or_sell:
                    # adjust price when buying
                    curr_price = ((price*trade_qty) + (curr_price*curr_qty)) / (curr_qty+trade_qty)
                    curr_price = max(0.0, round(curr_price, market.base_precision))

                curr_qty += trade_qty if buy_or_sell else -trade_qty
                curr_qty = max(0.0, round(curr_qty, market.base_precision))
            else:
                curr_price = 0.0
                curr_qty = 0

            if not curr_price and trade_qty > 0:
                if asset.symbol == self._account.currency:
                    # last min default/alt price
                    curr_price = self.history_price(asset.symbol+self.account.alt_currency, timestamp)
                else:
                    if self._watcher:
                        # base price in quote at trade time
                        if self._watcher.has_instrument(asset.symbol+self._account.currency):
                            # direct
                            curr_price = self.history_price(asset.symbol+self._account.currency, timestamp)
                        elif self._watcher.has_instrument(self._account.currency+asset.symbol):
                            # indirect
                            curr_price = 1.0 / self.history_price(self._account.currency+asset.symbol, timestamp)
                        else:
                            curr_price = 0.0  # might not occurs
                            logger.warning("Unsupported asset " + asset.symbol)
                    else:
                        if self.has_market(asset.symbol+self._account.currency):
                            # direct
                            curr_price = self._markets[asset.symbol+self._account.currency].price
                        elif self.has_market(self._account.currency+asset.symbol):
                            # indirect
                            quote_price = 1.0 / self._markets[self._account.currency+asset.symbol].price
                        else:
                            quote_price = 0.0  # might not occurs
                            logger.warning("Unsupported quote asset " + market.quote)

            # update price
            asset.update_price(timestamp, trade_id, curr_price, asset.quote)

        # update qty
        if buy_or_sell:
            # more free
            asset.set_quantity(asset.locked, asset.free+trade_qty)
        else:
            # less free @todo manage locked part for limit orders
            asset.set_quantity(0.0, max(0.0, asset.quantity-trade_qty))
            # if order_type in (Order.ORDER_MARKET, Order.ORDER_STOP, Order.ORDER_TAKE_PROFIT):
            #   # taker, less free
            #   asset.set_quantity(asset.locked, max(0.0, asset.free-trade_qty)) 
            # else:
            #   # maket, less locked
            #   asset.set_quantity(max(0.0, asset.locked-trade_qty), asset.free)

        # update profit/loss
        if market:
            asset.update_profit_loss(market)

        return quote_price * trade_qty

    #
    # margin (possible hedging)
    #

    def __exec_margin_order(self, order, market, open_exec_price, close_exec_price):
        """
        Execute the order for margin position.
        @todo support of hedging else reduce first the opposite direction positions (FIFO method)
        """
        current_position = None
        positions = []

        self.lock()

        if order.position_id:
            current_position = self._positions.get(order.position_id)
        else:
            # @todo
            pass
            # # position of the same market on any directions
            # for k, pos in self._positions.items():
            #     if pos.symbol == order.symbol:
            #         positions.append(pos)

            # if order.hedging and market.hedging:
            #     pass
            # else:
            #     current_position = positions[-1] if positions else None

        if current_position and current_position.is_opened():
            # increase or reduce the current position
            org_quantity = current_position.quantity
            exec_price = 0.0

            #
            # and adjust the position quantity (no hedging)
            #

            # price difference depending of the direction
            delta_price = 0
            if current_position.direction == Position.LONG:
                delta_price = close_exec_price - current_position.entry_price
                # logger.debug("cl", delta_price, " use ", close_exec_price, " other ", open_exec_price, close_exec_price < open_exec_price)
            elif current_position.direction == Position.SHORT:
                delta_price = current_position.entry_price - close_exec_price
                # logger.debug("cs", delta_price, " use ", close_exec_price, " other ", open_exec_price, close_exec_price < open_exec_price)

            # keep for percent calculation
            prev_entry_price = current_position.entry_price or close_exec_price
            leverage = order.leverage

            # most of thoose data rarely change except the base_exchange_rate
            value_per_pip = market.value_per_pip
            contract_size = market.contract_size
            lot_size = market.lot_size
            one_pip_means = market.one_pip_means
            base_exchange_rate = market.base_exchange_rate
            margin_factor = market.margin_factor

            # logger.debug(order.symbol, bid_price, ofr_price, open_exec_price, close_exec_price, delta_price, current_position.entry_price, order.price)
            realized_position_cost = 0.0  # realized cost of the position in base currency

            # effective meaning of delta price in base currency
            effective_price = (delta_price / one_pip_means) * value_per_pip

            # in base currency
            position_gain_loss = 0.0

            if order.direction == current_position.direction:
                # first, same direction, increase the position
                # it's what we have really buy
                realized_position_cost = order.quantity * (lot_size * contract_size)  # in base currency

                # check available margin
                margin_cost = realized_position_cost * margin_factor / base_exchange_rate

                if not self.has_margin(margin_cost):
                    # and then rejected order
                    self.unlock()

                    self.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, self.name, (order.symbol, order.ref_order_id))

                    logger.error("Not enought free margin for %s need %s but have %s!" % (order.symbol, margin_cost, self.account.margin_balance))
                    return False

                # still in long, position size increase and adjust the entry price
                entry_price = ((current_position.entry_price * current_position.quantity) + (open_exec_price * order.quantity)) / 2
                current_position.entry_price = entry_price
                current_position.quantity += order.quantity

                # directly executed quantity
                order.executed = order.quantity
                exec_price = open_exec_price

                # increase used margin
                self.account.add_used_margin(margin_cost)
            else:
                # different direction
                if current_position.quantity > order.quantity:
                    # first case the direction still the same, reduce the position and the margin
                    # take the profit/loss from the difference by order.quantity and adjust the entry price and quantity
                    position_gain_loss = effective_price * order.quantity

                    # it's what we have really closed
                    realized_position_cost = order.quantity * (lot_size * contract_size)  # in base currency

                    # and decrease used margin
                    self.account.add_used_margin(-realized_position_cost * margin_factor / base_exchange_rate)

                    # entry price might not move...
                    # current_position.entry_price = ((current_position.entry_price * current_position.quantity) - (close_exec_price * order.quantity)) / 2
                    current_position.quantity -= order.quantity
                    exec_price = close_exec_price

                    # directly executed quantity
                    order.executed = order.quantity

                elif current_position.quantity == order.quantity:
                    # second case the position is closed, exact quantity in the opposite direction

                    position_gain_loss = effective_price * current_position.quantity
                    current_position.quantity = 0.0

                    # it's what we have really closed
                    realized_position_cost = order.quantity * (lot_size * contract_size)  # in base currency

                    # directly executed quantity
                    order.executed = order.quantity
                    exec_price = close_exec_price

                    # and decrease used margin
                    self.account.add_used_margin(-realized_position_cost * margin_factor / base_exchange_rate)
                else:
                    # third case the position is reversed
                    # 1) get the profit loss
                    position_gain_loss = effective_price * current_position.quantity

                    # it's what we have really closed
                    realized_position_cost = order.quantity * (lot_size * contract_size)  # in base currency

                    # first decrease of released margin
                    self.account.add_used_margin(-realized_position_cost * margin_factor / base_exchange_rate)

                    # 2) adjust the position entry
                    current_position.quantity = order.quantity - current_position.quantity
                    current_position.entry_price = open_exec_price

                    # 3) the direction is now at opposite
                    current_position.direction = order.direction

                    # directly executed quantity
                    order.executed = order.quantity
                    exec_price = open_exec_price

                    # next increase margin of the new volume
                    self.account.add_used_margin((order.quantity * lot_size * contract_size * margin_factor) / base_exchange_rate)

            # transaction time is current timestamp
            order.transact_time = self.timestamp

            #order.set_position_id(current_position.position_id)

            if position_gain_loss != 0.0 and realized_position_cost > 0.0:
                # ratio
                gain_loss_rate = position_gain_loss / realized_position_cost
                relative_gain_loss_rate = delta_price / prev_entry_price

                # if maker close (limit+post-order) (for now same as market)
                current_position.profit_loss = position_gain_loss
                current_position.profit_loss_rate = gain_loss_rate

                # if taker close (market)
                current_position.profit_loss_market = position_gain_loss
                current_position.profit_loss_market_rate = gain_loss_rate

                self.account.add_realized_profit_loss(position_gain_loss / base_exchange_rate)

                # display only for debug
                if position_gain_loss > 0.0:
                    Terminal.inst().high("Close profitable position with %.2f on %s (%.2fpips) (%.2f%%) at %s" % (
                        position_gain_loss, order.symbol, delta_price/one_pip_means, gain_loss_rate*100.0, market.format_price(close_exec_price)), view='debug')
                elif position_gain_loss < 0.0:
                    Terminal.inst().low("Close loosing position with %.2f on %s (%.2fpips) (%.2f%%) at %s" % (
                        position_gain_loss, order.symbol, delta_price/one_pip_means, gain_loss_rate*100.0, market.format_price(close_exec_price)), view='debug')

                Terminal.inst().info("Account balance %.2f / Margin balance %.2f" % (self.account.balance, self.account.margin_balance), view='debug')
            else:
                gain_loss_rate = 0.0

            #
            # history
            #

            # and keep for history (backtesting reporting)
            history = PaperTraderHistoryEntry(order, self.account.balance, self.account.margin_balance, delta_price/one_pip_means,
                    gain_loss_rate, position_gain_loss, position_gain_loss/base_exchange_rate)

            self._history.add(history)

            # unlock before notify signals
            self.unlock()

            result = True

            #
            # order signal (SIGNAL_ORDER_OPENED+DELETED because we assume fully completed)
            #

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'direction': order.direction,
                'timestamp': order.created_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force
            }

            # signal as watcher service (opened + fully traded qty)
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (order.symbol, order_data, order.ref_order_id))

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'trade-id': 0,
                'direction': order.direction,
                'timestamp': order.transact_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'exec-price': exec_price,
                'avg-price': current_position.entry_price,
                'filled': order.executed,
                'cumulative-filled': order.executed,
                'quote-transacted': realized_position_cost,  # its margin
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force,
                'commission-amount': 0,  # @todo
                'commission-asset': self.account.currency
            }

            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (order.symbol, order_data, order.ref_order_id))

            #
            # position signal
            #

            # signal as watcher service
            if current_position.quantity <= 0:
                # closed position
                position_data = {
                    'id': current_position.position_id,
                    'symbol': current_position.symbol,
                    'direction': current_position.direction,
                    'timestamp': order.transact_time,
                    'quantity': 0,
                    'avg-entry-price': current_position.entry_price,
                    'avg-exit-price': current_position.exit_price,
                    'exec-price': exec_price,
                    'stop-loss': None,
                    'take-profit': None,
                    'profit-loss': current_position.profit_loss,
                    'profit-loss-currency': market.quote
                }

                self.service.watcher_service.notify(Signal.SIGNAL_POSITION_DELETED, self.name, (order.symbol, position_data, order.ref_order_id))
            else:
                # updated position
                position_data = {
                    'id': current_position.position_id,
                    'symbol': current_position.symbol,
                    'direction': current_position.direction,
                    'timestamp': order.transact_time,
                    'quantity': current_position.quantity,
                    # 'avg-price': current_position.entry_price,
                    'avg-entry-price': current_position.entry_price,
                    'avg-exit-price': current_position.exit_price,
                    'exec-price': exec_price,
                    'stop-loss': current_position.stop_loss,
                    'take-profit': current_position.take_profit,
                    'profit-loss': current_position.profit_loss,
                    'profit-loss-currency': market.quote
                }

                self.service.watcher_service.notify(Signal.SIGNAL_POSITION_UPDATED, self.name, (order.symbol, position_data, order.ref_order_id))

            # and then deleted order
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (order.symbol, order.order_id, ""))

            # if position is empty -> closed -> delete it
            if current_position.quantity <= 0.0:
                self.lock()

                current_position.exit(None)

                if current_position.position_id in self._positions:
                    del self._positions[current_position.position_id]

                self.unlock()
        else:
            # get a new distinct position id
            position_id = "siis_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n')

            # it's what we have really buy
            realized_position_cost = order.quantity * (market.lot_size * market.contract_size)  # in base currency

            # check available margin
            margin_cost = realized_position_cost * market.margin_factor / market.base_exchange_rate

            if not self.has_margin(margin_cost):
                # and then rejected order
                self.unlock()

                self.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, self.name, (order.symbol, order.ref_order_id))

                logger.error("Not enought free margin for %s need %s but have %s!" % (order.symbol, margin_cost, self.account.margin_balance))
                return False

            # create a new position at market
            position = Position(self)
            position.symbol = order.symbol

            position.set_position_id(position_id)
            position.set_key(self.service.gen_key())

            position.entry(order.direction, order.symbol, order.quantity)
            position.leverage = order.leverage

            position.created_time = self.timestamp

            account_currency = self.account.currency

            # long are open on ofr and short on bid
            position.entry_price = market.open_exec_price(order.direction)
            # logger.debug("%s %f %f %f %i" % ("el" if position.direction>0 else "es", position.entry_price, market.bid, market.ofr, market.bid < market.ofr))

            # transaction time is creation position date time
            order.transact_time = position.created_time
            order.set_position_id(position_id)

            # directly executed quantity
            order.executed = order.quantity

            self._positions[position_id] = position

            # increase used margin
            self.account.add_used_margin(margin_cost)

            #
            # history
            #

            history = PaperTraderHistoryEntry(order, self.account.balance, self.account.margin_balance)
            self._history.add(history)

            # unlock before notify signals
            self.unlock()

            result = True

            #
            # order signal (SIGNAL_ORDER_OPENED+TRADED+DELETED, fully completed)
            #

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'direction': order.direction,
                'timestamp': order.created_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force
            }

            # signal as watcher service (opened + fully traded qty)
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (order.symbol, order_data, order.ref_order_id))

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'trade-id': 0,
                'direction': order.direction,
                'timestamp': order.transact_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'exec-price': position.entry_price,
                'avg-price': position.entry_price,
                'filled': order.executed,
                'cumulative-filled': order.executed,
                'quote-transacted': realized_position_cost,  # its margin
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force,
                'commission-amount': 0,  # @todo
                'commission-asset': self.account.currency
            }

            #logger.info("%s %s %s" % (position.entry_price, position.quantity, order.direction))
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (order.symbol, order_data, order.ref_order_id))

            #
            # position signal
            #

            position_data = {
                'id': position.position_id,
                'symbol': position.symbol,
                'direction': position.direction,
                'timestamp': order.transact_time,
                'quantity': position.quantity,
                'exec-price': position.entry_price,
                'stop-loss': position.stop_loss,
                'take-profit': position.take_profit,
                'avg-entry-price': position.entry_price,
                'profit-loss': 0.0,
                'profit-loss-currency': market.quote
            }

            # signal as watcher service (position opened fully completed)
            self.service.watcher_service.notify(Signal.SIGNAL_POSITION_OPENED, self.name, (order.symbol, position_data, order.ref_order_id))

            # and then deleted order
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (order.symbol, order.order_id, ""))

        return result

    #
    # indivisible margin (not heding possible, single merged position)
    #

    def __exec_ind_margin_order(self, order, market, open_exec_price, close_exec_price):
        """
        Execute the order for indivisable margin position.
        @todo update to support only indivisible margin order
        """
        current_position = None
        positions = []

        self.lock()

        if order.symbol:
            # in that case position is identifier by its market
            current_position = self._positions.get(order.symbol)
 
        if current_position and current_position.is_opened():
            # increase or reduce the current position
            org_quantity = current_position.quantity
            exec_price = 0.0

            #
            # and adjust the position quantity (no possible hedging)
            #

            # price difference depending of the direction
            delta_price = 0
            if current_position.direction == Position.LONG:
                delta_price = close_exec_price - current_position.entry_price
                # logger.debug("cl", delta_price, " use ", close_exec_price, " other ", open_exec_price, close_exec_price < open_exec_price)
            elif current_position.direction == Position.SHORT:
                delta_price = current_position.entry_price - close_exec_price
                # logger.debug("cs", delta_price, " use ", close_exec_price, " other ", open_exec_price, close_exec_price < open_exec_price)

            # keep for percent calculation
            prev_entry_price = current_position.entry_price or close_exec_price
            leverage = order.leverage

            # most of thoose data rarely change except the base_exchange_rate
            value_per_pip = market.value_per_pip
            contract_size = market.contract_size
            lot_size = market.lot_size
            one_pip_means = market.one_pip_means
            base_exchange_rate = market.base_exchange_rate
            margin_factor = market.margin_factor

            # logger.debug(order.symbol, bid_price, ofr_price, open_exec_price, close_exec_price, delta_price, current_position.entry_price, order.price)
            realized_position_cost = 0.0  # realized cost of the position in base currency

            # effective meaning of delta price in base currency
            effective_price = (delta_price / one_pip_means) * value_per_pip

            # in base currency
            position_gain_loss = 0.0

            if order.direction == current_position.direction:
                # first, same direction, increase the position
                # it's what we have really buy
                realized_position_cost = order.quantity * (lot_size * contract_size)  # in base currency

                # check available margin
                margin_cost = realized_position_cost * margin_factor / base_exchange_rate

                if not self.has_margin(margin_cost):
                    # and then rejected order
                    self.unlock()

                    self.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, self.name, (order.symbol, order.ref_order_id))

                    logger.error("Not enought free margin for %s need %s but have %s!" % (order.symbol, margin_cost, self.account.margin_balance))
                    return False

                # still in long, position size increase and adjust the entry price
                entry_price = ((current_position.entry_price * current_position.quantity) + (open_exec_price * order.quantity)) / 2
                current_position.entry_price = entry_price
                current_position.quantity += order.quantity

                # directly executed quantity
                order.executed = order.quantity
                exec_price = open_exec_price

                # increase used margin
                self.account.add_used_margin(margin_cost)
            else:
                # different direction
                if current_position.quantity > order.quantity:
                    # first case the direction still the same, reduce the position and the margin
                    # take the profit/loss from the difference by order.quantity and adjust the entry price and quantity
                    position_gain_loss = effective_price * order.quantity

                    # it's what we have really closed
                    realized_position_cost = order.quantity * (lot_size * contract_size)  # in base currency

                    # and decrease used margin
                    self.account.add_used_margin(-realized_position_cost * margin_factor / base_exchange_rate)

                    # entry price might not move...
                    # current_position.entry_price = ((current_position.entry_price * current_position.quantity) - (close_exec_price * order.quantity)) / 2
                    current_position.quantity -= order.quantity
                    exec_price = close_exec_price

                    # directly executed quantity
                    order.executed = order.quantity

                elif current_position.quantity == order.quantity:
                    # second case the position is closed, exact quantity in the opposite direction

                    position_gain_loss = effective_price * current_position.quantity
                    current_position.quantity = 0.0

                    # it's what we have really closed
                    realized_position_cost = order.quantity * (lot_size * contract_size)  # in base currency

                    # directly executed quantity
                    order.executed = order.quantity
                    exec_price = close_exec_price

                    # and decrease used margin
                    self.account.add_used_margin(-realized_position_cost * margin_factor / base_exchange_rate)
                else:
                    # third case the position is reversed
                    # 1) get the profit loss
                    position_gain_loss = effective_price * current_position.quantity

                    # it's what we have really closed
                    realized_position_cost = order.quantity * (lot_size * contract_size)  # in base currency

                    # first decrease of released margin
                    self.account.add_used_margin(-realized_position_cost * margin_factor / base_exchange_rate)

                    # 2) adjust the position entry
                    current_position.quantity = order.quantity - current_position.quantity
                    current_position.entry_price = open_exec_price

                    # 3) the direction is now at opposite
                    current_position.direction = order.direction

                    # directly executed quantity
                    order.executed = order.quantity
                    exec_price = open_exec_price

                    # next increase margin of the new volume
                    self.account.add_used_margin((order.quantity * lot_size * contract_size * margin_factor) / base_exchange_rate)

            # transaction time is current timestamp
            order.transact_time = self.timestamp

            #order.set_position_id(current_position.position_id)

            if position_gain_loss != 0.0 and realized_position_cost > 0.0:
                # ratio
                gain_loss_rate = position_gain_loss / realized_position_cost
                relative_gain_loss_rate = delta_price / prev_entry_price

                # if maker close (limit+post-order) (for now same as market)
                current_position.profit_loss = position_gain_loss
                current_position.profit_loss_rate = gain_loss_rate

                # if taker close (market)
                current_position.profit_loss_market = position_gain_loss
                current_position.profit_loss_market_rate = gain_loss_rate

                self.account.add_realized_profit_loss(position_gain_loss / base_exchange_rate)

                # display only for debug
                if position_gain_loss > 0.0:
                    Terminal.inst().high("Close profitable position with %.2f on %s (%.2fpips) (%.2f%%) at %s" % (
                        position_gain_loss, order.symbol, delta_price/one_pip_means, gain_loss_rate*100.0, market.format_price(close_exec_price)), view='debug')
                elif position_gain_loss < 0.0:
                    Terminal.inst().low("Close loosing position with %.2f on %s (%.2fpips) (%.2f%%) at %s" % (
                        position_gain_loss, order.symbol, delta_price/one_pip_means, gain_loss_rate*100.0, market.format_price(close_exec_price)), view='debug')

                Terminal.inst().info("Account balance %.2f / Margin balance %.2f" % (self.account.balance, self.account.margin_balance), view='debug')
            else:
                gain_loss_rate = 0.0

            #
            # history
            #

            # and keep for history (backtesting reporting)
            history = PaperTraderHistoryEntry(order, self.account.balance, self.account.margin_balance, delta_price/one_pip_means,
                    gain_loss_rate, position_gain_loss, position_gain_loss/base_exchange_rate)

            self._history.add(history)

            # unlock before notify signals
            self.unlock()

            result = True

            #
            # order signal (SIGNAL_ORDER_OPENED+DELETED because we assume fully completed)
            #

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'direction': order.direction,
                'timestamp': order.created_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force
            }

            # signal as watcher service (opened + fully traded qty)
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (order.symbol, order_data, order.ref_order_id))

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'trade-id': 0,
                'direction': order.direction,
                'timestamp': order.transact_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'exec-price': exec_price,
                'avg-price': exec_price,  # current_position.entry_price,
                'filled': order.executed,
                'cumulative-filled': order.executed,
                'quote-transacted': realized_position_cost,  # its margin
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force,
                'commission-amount': 0,  # @todo
                'commission-asset': self.account.currency
            }

            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (order.symbol, order_data, order.ref_order_id))

            #
            # position signal
            #

            # signal as watcher service
            if current_position.quantity <= 0:
                # closed position
                position_data = {
                    'id': current_position.position_id,
                    'symbol': current_position.symbol,
                    'direction': current_position.direction,
                    'timestamp': order.transact_time,
                    'quantity': 0,
                    'exec-price': exec_price,
                    'stop-loss': None,
                    'take-profit': None
                }

                self.service.watcher_service.notify(Signal.SIGNAL_POSITION_DELETED, self.name, (order.symbol, position_data, order.ref_order_id))
            else:
                # updated position
                position_data = {
                    'id': current_position.position_id,
                    'symbol': current_position.symbol,
                    'direction': current_position.direction,
                    'timestamp': order.transact_time,
                    'quantity': current_position.quantity,
                    # 'avg-price': current_position.entry_price,
                    'exec-price': exec_price,
                    'stop-loss': current_position.stop_loss,
                    'take-profit': current_position.take_profit,
                    # 'profit-loss': @todo here
                }

                self.service.watcher_service.notify(Signal.SIGNAL_POSITION_UPDATED, self.name, (order.symbol, position_data, order.ref_order_id))

            # and then deleted order
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (order.symbol, order.order_id, ""))

            # if position is empty -> closed -> delete it
            if current_position.quantity <= 0.0:
                self.lock()

                # take care this does not make an issue
                current_position.exit(None)

                if current_position.symbol in self._positions:
                    del self._positions[current_position.symbol]

                self.unlock()
        else:
            # unique position per market
            position_id = market.market_id

            # it's what we have really buy
            realized_position_cost = order.quantity * (market.lot_size * market.contract_size)  # in base currency

            # check available margin
            margin_cost = realized_position_cost * market.margin_factor / market.base_exchange_rate

            if not self.has_margin(margin_cost):
                # and then rejected order
                self.unlock()

                self.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, self.name, (order.symbol, order.ref_order_id))

                logger.error("Not enought free margin for %s need %s but have %s!" % (order.symbol, margin_cost, self.account.margin_balance))
                return False

            # create a new position at market
            position = Position(self)
            position.symbol = order.symbol

            position.set_position_id(position_id)
            position.set_key(self.service.gen_key())

            position.entry(order.direction, order.symbol, order.quantity)
            position.leverage = order.leverage

            position.created_time = self.timestamp

            account_currency = self.account.currency

            # long are open on ofr and short on bid
            exec_price = open_exec_price
            position.entry_price = exec_price
            # logger.debug("%s %f %f %f %i" % ("el" if position.direction>0 else "es", position.entry_price, market.bid, market.ofr, market.bid < market.ofr))

            # transaction time is creation position date time
            order.transact_time = position.created_time
            order.set_position_id(position_id)

            # directly executed quantity
            order.executed = order.quantity

            self._positions[position_id] = position

            # increase used margin
            self.account.add_used_margin(margin_cost)

            #
            # history
            #

            history = PaperTraderHistoryEntry(order, self.account.balance, self.account.margin_balance)
            self._history.add(history)

            # unlock before notify signals
            self.unlock()

            result = True

            #
            # order signal (SIGNAL_ORDER_OPENED+TRADED+DELETED, fully completed)
            #

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'direction': order.direction,
                'timestamp': order.created_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force
            }

            # signal as watcher service (opened + fully traded qty)
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (order.symbol, order_data, order.ref_order_id))

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'trade-id': 0,
                'direction': order.direction,
                'timestamp': order.transact_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'exec-price': position.entry_price,
                'avg-price': position.entry_price,
                'filled': order.executed,
                'cumulative-filled': order.executed,
                'quote-transacted': realized_position_cost,  # its margin
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force,
                'commission-amount': 0,  # @todo
                'commission-asset': self.account.currency
            }

            #logger.info("%s %s %s" % (position.entry_price, position.quantity, order.direction))
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (order.symbol, order_data, order.ref_order_id))

            #
            # position signal
            #

            position_data = {
                'id': position.position_id,
                'symbol': position.symbol,
                'direction': position.direction,
                'timestamp': order.transact_time,
                'quantity': position.quantity,
                'exec-price': position.entry_price,
                'stop-loss': position.stop_loss,
                'take-profit': position.take_profit
            }

            # signal as watcher service (position opened fully completed)
            self.service.watcher_service.notify(Signal.SIGNAL_POSITION_OPENED, self.name, (order.symbol, position_data, order.ref_order_id))

            # and then deleted order
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (order.symbol, order.order_id, ""))

        return result
