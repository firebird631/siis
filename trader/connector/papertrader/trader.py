# @date 2018-09-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Generic paper trader.

import base64
import copy
import json
import time
import uuid

from datetime import datetime

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from trader.trader import Trader

from .account import PaperTraderAccount
from terminal.terminal import Terminal
from trader.asset import Asset
from trader.order import Order
from trader.position import Position

from .papertraderhistory import PaperTraderHistory, PaperTraderHistoryEntry

from .papertraderindmargin import exec_indmargin_order
from .papertradermargin import exec_margin_order
from .papertraderposition import close_position
from .papertraderspot import exec_buysell_order

import logging
logger = logging.getLogger('siis.trader.papertrader')


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
                # remove empty and closed positions
                if position.quantity <= 0.0:
                    rm_list.append(k)
                else:
                    market = self._markets.get(position.symbol)
                    if market:
                        # update profit/loss of each position
                        position.update_profit_loss(market)

                        # managed position take-profit and stop-loss
                        if market.has_position and (position.take_profit or position.stop_loss):
                            open_exec_price = market.close_exec_price(position.direction)
                            close_exec_price = market.close_exec_price(position.direction)

                            order_type = None

                            if position.direction > 0:
                                if position.take_profit and close_exec_price >= position.take_profit:
                                    order_type = Order.ORDER_LIMIT

                                elif position.stop_loss and close_exec_price <= position.stop_loss:
                                    order_type = Order.ORDER_MARKET

                            elif position.direction < 0:
                                if position.take_profit and close_exec_price <= position.take_profit:
                                    order_type = Order.ORDER_LIMIT

                                elif position.stop_loss and close_exec_price >= position.stop_loss:
                                    order_type = Order.ORDER_MARKET

                            if order_type is not None:
                                if close_position(self, market, position, close_exec_price, order_type):
                                    rm_list.append(k)

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
                            exec_ind_margin_order(self, order, market, open_exec_price, close_exec_price)
                        else:
                            exec_margin_order(self, order, market, open_exec_price, close_exec_price)
                    elif not order.margin_trade and market.has_spot:
                        exec_buysell_order(self, order, market, open_exec_price, close_exec_price)

                    # fully executed
                    rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_LIMIT:
                    # limit
                    if ((order.direction == Position.LONG and open_exec_price <= order.price) or
                        (order.direction == Position.SHORT and open_exec_price >= order.price)):

                        # does not support the really offered qty, take all at current price in one shot
                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                exec_indmargin_order(self, order, market, open_exec_price, close_exec_price)
                            else:
                                exec_margin_order(self, order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            exec_buysell_order(self, order, market, open_exec_price, close_exec_price)

                        # fully executed
                        rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_STOP:
                    # trigger + market
                    if ((order.direction == Position.LONG and close_exec_price >= order.stop_price) or
                        (order.direction == Position.SHORT and close_exec_price <= order.stop_price)):

                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                exec_indmargin_order(self, order, market, open_exec_price, close_exec_price)
                            else:
                                exec_margin_order(self, order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            exec_buysell_order(self, order, market, open_exec_price, close_exec_price)

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
                                exec_indmargin_order(self, order, market, open_exec_price, close_exec_price)
                            else:
                                exec_margin_order(self, order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            exec_buysell_order(self, order, market, open_exec_price, close_exec_price)

                    # fully executed
                    rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_TAKE_PROFIT:
                    # opposite trigger + market
                    if ((order.direction == Position.LONG and close_exec_price <= order.stop_price) or
                        (order.direction == Position.SHORT and close_exec_price >= order.stop_price)):

                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                exec_indmargin_order(self, order, market, open_exec_price, close_exec_price)
                            else:
                                exec_margin_order(self, order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            exec_buysell_order(self, order, market, open_exec_price, close_exec_price)

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
                                exec_indmargin_order(self, order, market, open_exec_price, close_exec_price)
                            else:
                                exec_margin_order(self, order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                                exec_buysell_order(self, order, market, open_exec_price, close_exec_price)

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
        quantity = order.quantity
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
            # @todo add to orders for emulate the slippage

            if order.margin_trade and market.has_margin:
                if market.indivisible_position:
                    return exec_indmargin_order(self, order, market, open_exec_price, close_exec_price)
                else:
                    return exec_margin_order(self, order, market, open_exec_price, close_exec_price)
            elif not order.margin_trade and market.has_spot:
                return exec_buysell_order(self, order, market, open_exec_price, close_exec_price)
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

    def close_position(self, position_id, limit_price=None):
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

            if limit_price:
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
                open_exec_price = ofr_price   # bid_price
                close_exec_price = bid_price  # ofr_price
            elif order.direction == Position.SHORT:
                open_exec_price = bid_price   # ofr_price
                close_exec_price = ofr_price  # bid_price
            else:
                logger.error("Unsupported direction")
                return False

            if not open_exec_price or not close_exec_price:
                logger.error("No order execution price")
                return False

            if self._slippage > 0.0:
                # @todo deferred to update
                return False
            else:
                # immediate execution of the order
                if market.has_position:
                    # close isolated position
                    result = close_position(self, market, position, close_exec_price, Order.ORDER_MARKET)
                else:
                    # close position (could be using FIFO method)
                    result = exec_margin_order(self, order, market, open_exec_price, close_exec_price)
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
        if position:
            market = self.market(position.symbol)
            if market and market.has_position:
                if stop_loss_price:
                    position.stop_loss = stop_loss_price
                if take_profit_price:
                    position.take_profit = take_profit_price

                result = True

        self.unlock()

        return result

    def positions(self, market_id):
        """
        @deprecated
        """
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

    #
    # slots
    #

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
