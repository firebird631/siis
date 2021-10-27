# @date 2018-12-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade for margin.

from common.signal import Signal

from trader.order import Order
from .strategytrade import StrategyTrade

import logging
logger = logging.getLogger('siis.strategy.margintrade')


class StrategyMarginTrade(StrategyTrade):
    """
    Specialization for margin trading. 

    This type of trade is related to margin trading market, allowing or not hedging.
    Works with crypto margin brokers (kraken...).

    @todo do we need like with asset trade an exit_trades list to compute the axp and x values, because
        if we use cumulative-filled and avg-price we have the same problem here too.
    @todo have to check about position_updated qty with direction maybe or take care to have trade signal and 
        distinct entry from exit
    """

    __slots__ = 'create_ref_oid', 'stop_ref_oid', 'limit_ref_oid', 'create_oid', 'stop_oid', 'limit_oid', \
        'position_id', 'leverage', 'stop_order_qty', 'limit_order_qty'

    def __init__(self, timeframe):
        super().__init__(StrategyTrade.TRADE_MARGIN, timeframe)

        self.create_ref_oid = None
        self.stop_ref_oid = None
        self.limit_ref_oid = None

        self.create_oid = None  # related entry order id
        self.stop_oid = None    # related stop order id
        self.limit_oid = None   # related limit order id

        self.position_id = None  # related informal position id
        self.leverage = 1.0

        self.stop_order_qty = 0.0    # if stop_oid then this is the qty placed on the stop order
        self.limit_order_qty = 0.0   # if limit_oid then this is the qty placed on the limit order

    def open(self, trader, instrument, direction, order_type, order_price, quantity,
             take_profit, stop_loss, leverage=1.0, hedging=None):
        """
        Open a position or buy an asset.

        @param hedging If defined use the defined value else use the default from the market.
        """
        if self._entry_state != StrategyTrade.STATE_NEW:
            return False

        order = Order(trader, instrument.market_id)
        order.direction = direction
        order.price = order_price
        order.order_type = order_type
        order.quantity = quantity
        order.leverage = leverage
        order.margin_trade = True
        order.post_only = False

        if hedging:
            order.hedging = hedging

        # generated a reference order id
        trader.set_ref_order_id(order)
        self.create_ref_oid = order.ref_order_id

        self.dir = order.direction

        self.op = order.price     # retains the order price
        self.oq = order.quantity  # ordered quantity

        self.tp = take_profit
        self.sl = stop_loss

        self.leverage = leverage

        self._stats['entry-order-type'] = order.order_type

        if trader.create_order(order, instrument):
            # keep the related create position identifier if available
            self.create_oid = order.order_id
            self.position_id = order.position_id

            if not self.eot and order.created_time:
                # only at the first open
                self.eot = order.created_time

            return True
        else:
            self._entry_state = StrategyTrade.STATE_REJECTED
            return False

    def reopen(self, trader, instrument, quantity):
        if self._entry_state != StrategyTrade.STATE_CANCELED:
            return False

        # reset
        self._entry_state = StrategyTrade.STATE_NEW
        self.eot = 0

        order = Order(trader, instrument.market_id)
        order.direction = self.dir
        order.price = self.op
        order.order_type = self._stats['entry-order-type']
        order.quantity = quantity
        order.post_only = False
        order.margin_trade = True
        order.leverage = self.leverage

        # generated a reference order id
        trader.set_ref_order_id(order)
        self.create_ref_oid = order.ref_order_id

        self.oq = order.quantity  # ordered quantity

        if trader.create_order(order, instrument):
            self.create_oid = order.order_id
            self.position_id = order.position_id  # might be market-id

            if not self.eot and order.created_time:
                # only at the first open
                self.eot = order.created_time

            return True
        else:
            self._entry_state = StrategyTrade.STATE_REJECTED
            return False

    def remove(self, trader, instrument):
        """
        Remove the orders, but doesn't close the position.
        """
        error = False

        if self.create_oid:
            # cancel the remaining buy order
            if trader.cancel_order(self.create_oid, instrument):
                self.create_ref_oid = None
                self.create_oid = None

                if self.e <= 0:
                    # no entry qty processed, entry canceled
                    self._entry_state = StrategyTrade.STATE_CANCELED
                else:
                    # cancel a partially filled trade means it is then fully filled
                    self._entry_state = StrategyTrade.STATE_FILLED
            else:
                error = True

        if self.stop_oid:
            # cancel the stop order
            if trader.cancel_order(self.stop_oid, instrument):
                self.stop_ref_oid = None
                self.stop_oid = None
                self.stop_order_qty = 0.0

                if self.e <= 0 and self.x <= 0:
                    # no exit qty
                    self._exit_state = StrategyTrade.STATE_CANCELED
                elif self.x >= self.e:
                    self._exit_state = StrategyTrade.STATE_FILLED
                else:
                    self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED
            else:
                error = True

        if self.limit_oid:
            # cancel the limit order
            if trader.cancel_order(self.limit_oid, instrument):
                self.limit_ref_oid = None
                self.limit_oid = None
                self.limit_order_qty = 0.0

                if self.e <= 0 and self.x <= 0:
                    # no exit qty
                    self._exit_state = StrategyTrade.STATE_CANCELED
                elif self.x >= self.e:
                    self._exit_state = StrategyTrade.STATE_FILLED
                else:
                    self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED
            else:
                error = True

        return not error

    def cancel_open(self, trader, instrument):
        if self.create_oid:
            # cancel the buy order
            if trader.cancel_order(self.create_oid, instrument):
                self.create_ref_oid = None
                self.create_oid = None

                if self.e <= 0:
                    # cancel a just opened trade means it is canceled
                    self._entry_state = StrategyTrade.STATE_CANCELED
                else:
                    # cancel a partially filled trade means it is then fully filled
                    self._entry_state = StrategyTrade.STATE_FILLED
            else:
                return False

        return True

    def modify_take_profit(self, trader, instrument, limit_price):
        if self.limit_oid:
            # cancel the limit order and create a new one
            if trader.cancel_order(self.limit_oid, instrument):
                self.limit_ref_oid = None
                self.limit_oid = None
                self.limit_order_qty = 0.0
            else:
                return self.ERROR

        if self.e == self.x:
            # all entry qty is filled
            return self.NOTHING_TO_DO

        if self.e < self.x:
            # something wrong but its ok
            return self.NOTHING_TO_DO

        if self.e > 0 and limit_price > 0.0:
            # only if filled entry partially or totally
            order = Order(self, instrument.market_id)
            order.direction = -self.direction
            order.order_type = Order.ORDER_LIMIT
            order.reduce_only = True
            order.quantity = self.e - self.x  # remaining
            order.price = limit_price
            order.leverage = self.leverage
            order.margin_trade = True

            trader.set_ref_order_id(order)
            self.limit_ref_oid = order.ref_order_id

            self._stats['take-profit-order-type'] = order.order_type

            if trader.create_order(order, instrument):
                self.limit_oid = order.order_id
                self.limit_order_qty = order.quantity

                self.last_tp_ot[0] = order.created_time
                self.last_tp_ot[1] += 1

                self.tp = limit_price

                return self.ACCEPTED
            else:
                self.limit_ref_oid = None
                self.limit_order_qty = 0.0

                return self.REJECTED

        return self.NOTHING_TO_DO

    def modify_stop_loss(self, trader, instrument, stop_price):
        if self.stop_oid:
            # cancel the stop order and create a new one
            if trader.cancel_order(self.stop_oid, instrument):
                self.stop_ref_oid = None
                self.stop_oid = None
            else:
                return self.ERROR

        if self.e == self.x:
            # all entry qty is filled
            return self.NOTHING_TO_DO

        if self.e < self.x:
            # something wrong but its ok
            return self.NOTHING_TO_DO

        if self.e > 0 and stop_price > 0.0:
            # only if filled entry partially or totally
            order = Order(self, instrument.market_id)
            order.direction = -self.direction
            order.order_type = Order.ORDER_STOP
            order.reduce_only = True
            order.quantity = self.e - self.x  # remaining
            order.stop_price = stop_price
            order.leverage = self.leverage
            order.margin_trade = True

            trader.set_ref_order_id(order)
            self.stop_ref_oid = order.ref_order_id

            self._stats['stop-order-type'] = order.order_type

            if trader.create_order(order, instrument):
                self.stop_oid = order.order_id
                self.stop_order_qty = order.quantity
                
                self.last_stop_ot[0] = order.created_time
                self.last_stop_ot[1] += 1

                self.sl = stop_price

                return self.ACCEPTED
            else:
                self.stop_ref_oid = None
                self.stop_order_qty = 0.0

                return self.REJECTED

        return self.NOTHING_TO_DO

    def close(self, trader, instrument):
        """
        Close the position and cancel the related orders.
        """
        if self._closing:
            # already closing order
            return self.NOTHING_TO_DO

        if self.create_oid:
            # cancel the remaining buy order
            if trader.cancel_order(self.create_oid, instrument):
                self.create_ref_oid = None
                self.create_oid = None

                self._entry_state = StrategyTrade.STATE_CANCELED
            else:
                return self.ERROR

        if self.stop_oid:
            # cancel the stop order
            if trader.cancel_order(self.stop_oid, instrument):
                self.stop_ref_oid = None
                self.stop_oid = None
            else:
                return self.ERROR

        if self.limit_oid:
            # cancel the limit order
            if trader.cancel_order(self.limit_oid, instrument):
                self.limit_ref_oid = None

        if self.e - self.x > 0.0:
            # bitmex case no have position id
            order = Order(trader, instrument.market_id)
            order.direction = -self.dir  # neg dir
            order.order_type = Order.ORDER_MARKET
            order.reduce_only = True
            order.quantity = self.e - self.x  # remaining qty
            order.leverage = self.leverage
            order.margin_trade = True

            # generated a reference order id
            trader.set_ref_order_id(order)
            self.stop_ref_oid = order.ref_order_id

            self._stats['stop-order-type'] = order.order_type

            if trader.create_order(order, instrument):
                self.stop_oid = order.order_id
                self.stop_order_qty = order.quantity

                # closing order defined
                self._closing = True

                return self.ACCEPTED
            else:
                self.stop_ref_oid = None
                self.stop_order_qty = 0.0

                return self.REJECTED

        return self.NOTHING_TO_DO

    def has_stop_order(self):
        return (self.stop_oid is not None and self.stop_oid != "")

    def has_limit_order(self):
        return (self.limit_oid is not None and self.limit_oid != "")

    def support_both_order(self):
        return True

    @classmethod
    def is_margin(cls):
        return True

    @classmethod
    def is_spot(cls):
        return False

    #
    # signal
    #

    def order_signal(self, signal_type, data, ref_order_id, instrument):
        if signal_type == Signal.SIGNAL_ORDER_OPENED:
            # already get at the return of create_order
            if ref_order_id == self.create_ref_oid:
                self.create_oid = data['id']

                # init created timestamp at the create order open
                if not self.eot:
                    self.eot = data['timestamp']

                if data.get('stop-loss'):
                    self.sl = data['stop-loss']

                if data.get('take-profit'):
                    self.tp = data['take-profit']

                self._entry_state = StrategyTrade.STATE_OPENED

            elif ref_order_id == self.stop_ref_oid:
                self.stop_oid = data['id']

                if not self.xot:
                    self.xot = data['timestamp']

            elif ref_order_id == self.limit_ref_oid:
                self.limit_oid = data['id']

                if not self.xot:
                    self.xot = data['timestamp']

        elif signal_type == Signal.SIGNAL_ORDER_DELETED:
            # order is no longer active
            if data == self.create_oid:
                self.create_ref_oid = None                
                self.create_oid = None
                self._entry_state = StrategyTrade.STATE_DELETED

            elif data == self.limit_oid:
                self.limit_ref_oid = None
                self.limit_oid = None

            elif data == self.stop_oid:
                self.stop_ref_oid = None
                self.stop_oid = None

        elif signal_type == Signal.SIGNAL_ORDER_CANCELED:
            # order is no longer active
            if data == self.create_oid:
                self.create_ref_oid = None                
                self.create_oid = None
                self._entry_state = StrategyTrade.STATE_CANCELED

            elif data == self.limit_oid:
                self.limit_ref_oid = None
                self.limit_oid = None

            elif data == self.stop_oid:
                self.stop_ref_oid = None
                self.stop_oid = None

        elif signal_type == Signal.SIGNAL_ORDER_UPDATED:
            # order price/qty modified, cannot really be used because the strategy might
            # cancel the trade or create another one.
            # for the qty we could have a remaining_qty member, then comparing
            pass

        elif signal_type == Signal.SIGNAL_ORDER_TRADED:
            # order fully or partially filled
            filled = 0

            if data['id'] == self.create_oid:
                # a single order for the entry, then its OK and prefered to uses cumulative-filled and avg-price
                # because precision comes from the broker
                if data.get('cumulative-filled') is not None and data['cumulative-filled'] > 0:
                    filled = data['cumulative-filled'] - self.e  # compute filled qty
                elif data.get('filled') is not None and data['filled'] > 0:
                    filled = data['filled']
                else:
                    filled = 0

                if data.get('avg-price') is not None and data['avg-price'] > 0:
                    # in that case we have avg-price already computed
                    self.aep = data['avg-price']

                elif data.get('exec-price') is not None and data['exec-price'] > 0:
                    # compute the average price
                    self.aep = ((self.aep * self.e) + (data['exec-price'] * filled)) / (self.e + filled)
                else:
                    # no have uses order price
                    self.aep = self.op

                # cumulative filled entry qty
                if data.get('cumulative-filled') is not None:
                    self.e = data.get('cumulative-filled')
                elif filled > 0:
                    self.e = instrument.adjust_quantity(self.e + filled)

                if filled > 0:
                    # probably need to update exit orders
                    self._dirty = True

                logger.info("Entry avg-price=%s cum-filled=%s" % (self.aep, self.e))

                if self.e >= self.oq:
                    self._entry_state = StrategyTrade.STATE_FILLED

                    # bitmex does not send ORDER_DELETED signal, cleanup here
                    self.create_oid = None
                    self.create_ref_oid = None
                else:
                    self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED

                # retains the trade timestamp
                if not self._stats['first-realized-entry-timestamp']:
                    self._stats['first-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                self._stats['last-realized-entry-timestamp'] = data.get('timestamp', 0.0)

            elif data['id'] == self.limit_oid or data['id'] == self.stop_oid:
                # either we have 'filled' component (partial qty) or the 'cumulative-filled' or the twices
                if data.get('cumulative-filled') is not None and data['cumulative-filled'] > 0:
                    filled = data['cumulative-filled'] - self.x   # computed filled qty
                elif data.get('filled') is not None and data['filled'] > 0:
                    filled = data['filled']
                else:
                    filled = 0

                if data.get('avg-price') is not None and data['avg-price'] > 0:
                    # recompute profit-loss
                    if self.dir > 0:
                        self.pl = (data['avg-price'] - self.aep) / self.aep
                    elif self.dir < 0:
                        self.pl = (self.aep - data['avg-price']) / self.aep

                    # in that case we have avg-price already computed
                    self.axp = data['avg-price']

                elif data.get('exec-price') is not None and data['exec-price'] > 0:
                    # increase/decrease profit/loss (over entry executed quantity)
                    if self.dir > 0:
                        self.pl += ((data['exec-price'] * filled) - (self.aep * filled)) / (self.aep * self.e)
                    elif self.dir < 0:
                        self.pl += ((self.aep * filled) - (data['exec-price'] * filled)) / (self.aep * self.e)

                    # compute the average price
                    self.axp = ((self.axp * self.x) + (data['exec-price'] * filled)) / (self.x + filled)

                # cumulative filled exit qty
                if data.get('cumulative-filled') is not None:
                    self.x = data.get('cumulative-filled')
                elif filled > 0:
                    self.x = instrument.adjust_quantity(self.x + filled)

                logger.info("Exit avg-price=%s cum-filled=%s" % (self.axp, self.x))

                if self.x >= self.oq:
                    self._exit_state = StrategyTrade.STATE_FILLED

                    # bitmex does not send ORDER_DELETED signal, cleanup here
                    if data['id'] == self.limit_oid:
                        self.limit_oid = None
                        self.limit_ref_oid = None
                    elif data['id'] == self.stop_oid:
                        self.stop_oid = None
                        self.stop_ref_oid = None
                else:
                    self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED

                # retains the trade timestamp
                if not self._stats['first-realized-exit-timestamp']:
                    self._stats['first-realized-exit-timestamp'] = data.get('timestamp', 0.0)

                self._stats['last-realized-exit-timestamp'] = data.get('timestamp', 0.0)

    def position_signal(self, signal_type, data, ref_order_id, instrument):
        if signal_type == Signal.SIGNAL_POSITION_OPENED:
            self.position_id = data['id']

            if data.get('profit-loss'):
                self._stats['unrealized-profit-loss'] = data['profit-loss']
            if data.get('profit-currency'):
                self._stats['profit-loss-currency'] = data['profit-currency']

        elif signal_type == Signal.SIGNAL_POSITION_UPDATED:
            # update the unrealized profit-loss in currency
            if data.get('profit-loss'):
                self._stats['unrealized-profit-loss'] = data['profit-loss']
            if data.get('profit-currency'):
                self._stats['profit-loss-currency'] = data['profit-currency']

        elif signal_type == Signal.SIGNAL_POSITION_DELETED:
            # no longer related position
            self.position_id = None

            if data.get('profit-loss'):
                self._stats['unrealized-profit-loss'] = data['profit-loss']
            if data.get('profit-currency'):
                self._stats['profit-loss-currency'] = data['profit-currency']

        elif signal_type == Signal.SIGNAL_POSITION_AMENDED:
            # might not occurs
            pass

    def is_target_order(self, order_id, ref_order_id):
        if order_id and (order_id == self.create_oid or order_id == self.stop_oid or order_id == self.limit_oid):
            return True

        if ref_order_id and (ref_order_id == self.create_ref_oid or ref_order_id == self.stop_ref_oid or ref_order_id == self.limit_ref_oid):
            return True

        return False

    def is_target_position(self, position_id, ref_order_id):
        if position_id and (position_id == self.position_id):
            return True

        if ref_order_id and (ref_order_id == self.create_ref_oid):
            return True

    #
    # persistence
    #

    def dumps(self):
        data = super().dumps()

        data['create-ref-oid'] = self.create_ref_oid
        data['stop-ref-oid'] = self.stop_ref_oid
        data['limit-ref-oid'] = self.limit_ref_oid

        data['create-oid'] = self.create_oid
        data['stop-oid'] = self.stop_oid
        data['limit-oid'] = self.limit_oid

        data['position-id'] = self.position_id

        data['stop-order-qty'] = self.stop_order_qty
        data['limit-order-qty'] = self.limit_order_qty

        return data

    def loads(self, data, strategy_trader, context_builder=None):
        if not super().loads(data, strategy_trader, context_builder):
            return False

        self.create_ref_oid = data.get('create-ref-oid')
        self.stop_ref_oid = data.get('stop-ref-oid')
        self.limit_ref_oid = data.get('limit-ref-oid')

        self.create_oid = data.get('create-oid')
        self.stop_oid = data.get('stop-oid')
        self.limit_oid = data.get('limit-oid')

        self.position_id = data.get('position-id')

        self.stop_order_qty = data.get('stop-order-qty', 0.0)
        self.limit_order_qty = data.get('limit-order-qty', 0.0)

        return True

    def check(self, trader, instrument):
        # @todo
        return 1

    #
    # stats
    #

    def update_stats(self, instrument, timestamp):
        super().update_stats(instrument, timestamp)

    def info_report(self, strategy_trader):
        data = super().info_report(strategy_trader)

        return data + (
            'Entry order id / ref : %s / %s' % (self.create_oid, self.create_ref_oid),
            'Stop order id / ref : %s / %s' % (self.stop_oid, self.stop_ref_oid),
            'Limit order id / ref : %s / %s' % (self.limit_oid, self.limit_ref_oid),
            'Position id : %s' % self.position_id,
        )
