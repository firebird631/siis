# @date 2018-12-28
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade for asset.

from notifier.signal import Signal
from database.database import Database

from trader.order import Order
from .strategytrade import StrategyTrade

import logging
logger = logging.getLogger('siis.strategy')


class StrategyAssetTrade(StrategyTrade):
    """
    Specialization for asset buy/sell trading.
    Only an initial buy order, and a single, either a stop or a take-profit order.
    """

    SELL_ORDER_NONE = 0
    SELL_ORDER_MARKET = 1
    SELL_ORDER_STOP_LOSS = 1
    SELL_ORDER_TAKE_PROFIT = 2

    def __init__(self, timeframe):
        super().__init__(StrategyTrade.TRADE_BUY_SELL, timeframe)

        self.buy_ref_oid = None
        self.sell_ref_oid = None

        self.buy_oid = None   # related buy order id
        self.sell_oid = None  # related sell order id

        self.sell_order_type = Order.ORDER_MARKET
        self.sell_order_qty = 0.0

    def open(self, trader, market_id, direction, order_type, order_price, quantity, take_profit, stop_loss, leverage=1.0, hedging=None):
        """
        Open a position or buy an asset.
        """
        order = Order(trader, market_id)
        order.direction = direction
        order.order_price = order_price
        order.order_type = order_type
        order.quantity = quantity
        order.leverage = leverage

        # if need to retry
        self._market_id = market_id
        self._order_type = order_type
        self._leverage = leverage

        # generated a reference order id
        trader.set_ref_order_id(order)
        self.buy_ref_oid = order.ref_order_id

        self.dir = order.direction
        self.q = order.quantity     # ordered quantity

        self.tp = take_profit
        self.sl = stop_loss
        self.op = order.order_price  # retains the order price

        self._stats['entry-maker'] = not order.is_market()

        if order_type == Order.ORDER_LIMIT:
            self._stats['order-limit-price'] = order_price

        if trader.create_order(order):
            if not self.open_time:
                # only at the first open
                self._open_time = order.created_time

            return True
        else:
            self._entry_state = StrategyTrade.STATE_REJECTED
            return False

    def remove(self, trader):
        if self.buy_oid:
            # cancel the remaining buy order
            if trader.cancel_order(self.sell_oid):
                # returns true, no need to wait signal confirmation
                self.buy_ref_oid = None
                self.buy_oid = None
                self._entry_state = StrategyTrade.STATE_DELETED

        if self.sell_oid:
            # cancel the sell order and create a new one
            if trader.cancel_order(self.sell_oid):
                # returns true, no need to wait signal confirmation
                self.sell_ref_oid = None
                self.sell_oid = None
                self._exit_state =StrategyTrade.STATE_DELETED

    def cancel_open(self, trader):
        if self.buy_oid:
            # cancel the buy order
            if trader.cancel_order(self.buy_oid):
                # returns true, no need to wait signal confirmation
                self.buy_oid = None
                self.buy_ref_oid = None
                
                self._entry_state = StrategyTrade.STATE_CANCELED
            else:
                return False

        return True

    def modify_take_profit(self, trader, market_id, price):
        self.tp = price

        if self.sell_oid:
            # cancel the sell order and create a new one
            if trader.cancel_order(self.sell_oid):
                self.sell_ref_oid = None
                self.sell_oid = None
                self.sell_order_type = Order.ORDER_MARKET
                self.sell_order_qty = 0.0

                self._exit_state = StrategyTrade.STATE_DELETED

        if self.e == self.x:
            # all entry qty is filled
            return True

        if self.e < self.x:
            # something wrong but its ok
            return False

        if price:
            order = Order(trader, market_id)
            order.direction = -self.dir  # neg dir
            order.order_type = Order.ORDER_LIMIT
            order.quantity = self.e - self.x  # remaining

            self._stats['exit-maker'] = not order.is_market()

            # generated a reference order id
            trader.set_ref_order_id(order)
            self.sell_ref_oid = order.ref_order_id

            if trader.create_order(order):
                self.sell_order_type = order.order_type
                self.sell_order_qty = order.quantity

                return True
            else:
                return False

        return True

    def modify_stop_loss(self, trader, market_id, price):
        self.sl = price

        if self.sell_oid:
            # cancel the sell order and create a new one
            if trader.cancel_order(self.sell_oid):
                # returns true, no need to wait signal confirmation
                self.sell_ref_oid = None
                self.sell_oid = None
                self.sell_order_type = Order.ORDER_MARKET
                self.sell_order_qty = 0.0

                self._exit_state = StrategyTrade.STATE_DELETED

        if self.e == self.x:
            # all entry qty is filled
            return True

        if self.e < self.x:
            # something wrong but its ok
            return False

        if price:
            order = Order(trader, market_id)
            order.direction = -self.dir  # neg dir
            order.order_type = Order.ORDER_STOP
            order.quantity = self.e - self.x  # remaining

            self._stats['exit-maker'] = not order.is_market()

            # generated a reference order id
            trader.set_ref_order_id(order)
            self.sell_ref_oid = order.ref_order_id

            if trader.create_order(order):
                self.sell_order_type = order.order_type
                self.sell_order_qty = order.quantity

                return True
            else:
                return False

        return True

    def close(self, trader, market_id):
        if self.sell_ref_oid:
            logger.error("Trade %s has already ordered an exit !" % self.id)
            return False

        if self.buy_oid:
            # cancel the remaining buy order
            if trader.cancel_order(self.sell_oid):
                self.buy_ref_oid = None
                self.buy_oid = None

                self._entry_state = StrategyTrade.STATE_CANCELED

        if self.sell_oid:
            # cancel the sell order and create a new one
            if trader.cancel_order(self.sell_oid):
                self.sell_ref_oid = None
                self.sell_oid = None
                self.sell_order_type = Order.ORDER_MARKET
                self.sell_order_qty = 0.0

                self._exit_state = StrategyTrade.STATE_CANCELED

        if self.e == self.x:
            # all entry qty is filled
            return True

        if self.e < self.x:
            # something wrong but its ok
            return False

        order = Order(trader, market_id)
        order.direction = -self.dir  # neg dir
        order.order_type = Order.ORDER_MARKET
        order.quantity = self.e - self.x  # remaining qty

        self._stats['exit-maker'] = not order.is_market()

        # generated a reference order id
        trader.set_ref_order_id(order)
        self.sell_ref_oid = order.ref_order_id

        if trader.create_order(order):
            self.sell_order_type = order.order_type
            self.sell_order_qty = order.quantity

            return True
        else:
            return False

    def is_closing(self):
        return self.sell_ref_oid is not None or self._exit_state == StrategyTrade.STATE_OPENED or self._exit_state == StrategyTrade.STATE_PARTIALLY_FILLED

    def is_target_order(self, order_id, ref_order_id):
        if order_id and (order_id == self.buy_oid or order_id == self.sell_oid):
            return True

        if ref_order_id and (ref_order_id == self.buy_ref_oid or ref_order_id == self.sell_ref_oid):
            return True

        return False

    def order_signal(self, signal_type, data, ref_order_id):
        if signal_type == Signal.SIGNAL_ORDER_OPENED:
            # already get at the return of create_order
            if ref_order_id == self.buy_ref_oid:  # data['direction'] > 0: 
                self.buy_oid = data['id']

                # last open order timestamp
                self.t = data['timestamp']

                if data.get('stop-loss'):
                    self.sl = data['stop-loss']

                if data.get('take-profit'):
                    self.tp = data['take-profit']

                self._entry_state = StrategyTrade.STATE_OPENED

            elif ref_order_id == self.sell_ref_oid:  # data['direction'] < 0:
                self.sell_oid = data['id']

                # self.t = data['timestamp']
                # self.q = data['quantity']

                self._exit_state = StrategyTrade.STATE_OPENED

        elif signal_type == Signal.SIGNAL_ORDER_TRADED:
            # update the trade quantity
            if data['id'] == self.buy_oid and 'filled' in data:
                if data.get('filled') is not None and data['filled'] > 0:
                    filled = data['filled']
                elif data.get('cumulative-filled') is not None and data['cumulative-filled'] > 0:
                    filled = data['cumulative-filled'] - self.e  # compute filled qty
                else:
                    filled = 0

                if data.get('exec-price') is not None and data['exec-price']:
                    # compute the average price whe increasing the position
                    self.p = ((self.p * self.e) + (data['exec-price'] * filled)) / (self.e + filled)
                elif data.get('avg-price') is not None and data['avg-price']:
                    # average price is directly given
                    self.p = data['avg-price']

                self.e += filled

                # commission asset is asset, have to reduce it from filled
                if data['commission-asset'] == data['symbol']:
                    self.e -= data['commission-amount']

                if self.e >= self.q:
                    self._entry_state = StrategyTrade.STATE_FILLED
                else:
                    self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED

            elif data['id'] == self.sell_oid and 'filled' in data:
                if data.get('filled') is not None and data['filled'] > 0:
                    filled = data['filled']
                elif data.get('cumulative-filled') is not None and data['cumulative-filled'] > 0:
                    filled = data['cumulative-filled'] - self.x  # compute filled qty
                else:
                    filled = 0

                if data.get('exec-price') is not None and data['exec-price']:
                    # profit/loss when reducing the position (over executed entry qty)
                    self.pl += ((data['exec-price'] * filled) - (self.p * self.e)) / (self.p * self.e)
                elif data.get('avg-price') is not None and data['avg-price']:
                    # average price is directly given
                    self.pl = ((data['avg-price'] * (self.x + filled)) - (self.p * self.e)) / (self.p * self.e)

                self.x += filled

                # commission asset is asset, have to reduce it from filled
                if data['commission-asset'] == data['symbol']:
                    self.x -= data['commission-amount']

                if self.x >= self.q:
                    self._exit_state = StrategyTrade.STATE_FILLED
                else:
                    self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED

        elif signal_type == Signal.SIGNAL_ORDER_UPDATED:
            # order price/qty modified @see comment on margintrade
            pass

        elif signal_type == Signal.SIGNAL_ORDER_DELETED:
            # order is not longer active
            if data == self.buy_oid:
                self.buy_ref_oid = None
                self.buy_oid = None
                self._entry_state = StrategyTrade.STATE_DELETED

            elif data == self.sell_oid:
                self.sell_ref_oid = None
                self.sell_oid = None
                self._exit_state = StrategyTrade.STATE_DELETED

        elif signal_type == Signal.SIGNAL_ORDER_REJECTED:
            # order is rejected
            if data == self.buy_ref_oid:
                self.buy_ref_oid = None
                self.buy_oid = None
                self._entry_state = StrategyTrade.STATE_REJECTED

            elif data == self.sell_ref_oid:
                self.sell_ref_oid = None
                self.sell_oid = None
                self._exit_state = StrategyTrade.STATE_REJECTED

        elif signal_type == Signal.SIGNAL_ORDER_CANCELED:
            # order is not longer active
            if data == self.buy_oid:
                self.buy_ref_oid = None
                self.buy_oid = None
                self._entry_state = StrategyTrade.STATE_CANCELED

            elif data == self.sell_oid:
                self.sell_ref_oid = None
                self.sell_oid = None
                self._exit_state = StrategyTrade.STATE_CANCELED

    def save(self, trader, market_id):
        pass  # @todo
