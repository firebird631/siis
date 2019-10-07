# @date 2018-12-28
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade for margin.

from notifier.signal import Signal
from database.database import Database

from trader.order import Order
from .strategytrade import StrategyTrade

import logging
logger = logging.getLogger('siis.strategy')


class StrategyMarginTrade(StrategyTrade):
    """
    Specialization for margin trading. 

    This type of trade is related to margin trading market, allowing or not hedging.

    @todo do we need like with asset trade an exit_trades list to compute the axp and x values, because
        if we use cumulative-filled and avg-price we have the same probleme here too.
    """

    __slots__ = 'create_ref_oid', 'stop_ref_oid', 'limit_ref_oid', 'create_oid', 'stop_oid', 'limit_oid', 'position_id', \
        'leverage', 'stop_order_qty', 'limit_order_qty'

    def __init__(self, timeframe):
        super().__init__(StrategyTrade.TRADE_MARGIN, timeframe)

        self.create_ref_oid = None
        self.stop_ref_oid = None
        self.limit_ref_oid = None

        self.create_oid = None  # related entry order id
        self.stop_oid = None    # related stop order id
        self.limit_oid = None   # related limit order id

        self.position_id = None  # related position id
        self.leverage = 1.0

        self.stop_order_qty = 0.0    # if stop_oid then this is the qty placed on the stop order
        self.limit_order_qty = 0.0   # if limit_oid then this is the qty placed on the limit order

    def open(self, trader, instrument, direction, order_type, order_price, quantity, take_profit, stop_loss, leverage=1.0, hedging=None):
        """
        Open a position or buy an asset.

        @param hedging If defined use the defined value else use the default from the market.
        """
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

        if trader.create_order(order):
            # keep the related create position identifier if available
            self.position_id = order.position_id

            if not self.eot and order.created_time:
                # only at the first open
                self.eot = order.created_time

            return True
        else:
            self._entry_state = StrategyTrade.STATE_REJECTED
            return False

    def remove(self, trader):
        """
        Remove the order, but doesn't close the position.
        """
        if self.create_oid:
            # cancel the remaining buy order
            if trader.cancel_order(self.create_oid):
                self.create_ref_oid = None
                self.create_oid = None

                if self.e <= 0:
                    # no entry qty processed, entry canceled
                    self._entry_state = StrategyTrade.STATE_CANCELED
                else:
                    # cancel a partially filled trade means it is then fully filled
                    self._entry_state = StrategyTrade.STATE_FILLED

        if self.stop_oid:
            # cancel the stop order
            if trader.cancel_order(self.stop_oid):
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

        if self.limit_oid:
            # cancel the limit order
            if trader.cancel_order(self.limit_oid):
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

    def cancel_open(self, trader):
        if self.create_oid:
            # cancel the buy order
            if trader.cancel_order(self.create_oid):
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
            if trader.cancel_order(self.limit_oid):
                self.limit_ref_oid = None
                self.limit_oid = None
                self.limit_order_qty = 0.0
            else:
                return False

        if self.e == self.x:
            # all entry qty is filled
            return True

        if self.e < self.x:
            # something wrong but its ok
            return False

        if self.position_id:
            # if not accepted as modification do it as limit order
            if trader.modify_position(self.position_id, take_profit_price=limit_price):
                self.tp = limit_price
                return True

        elif self.e > 0:
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

            self._stats['limit-order-type'] = order.order_type

            if trader.create_order(order):
                self.limit_oid = order.order_id
                self.limit_order_qty = order.quantity

                self.last_tp_ot[0] = order.created_time
                self.last_tp_ot[1] += 1

                self.tp = limit_price

                return True
            else:
                self.limit_ref_oid = None
                self.limit_order_qty = 0.0

        return False

    def modify_stop_loss(self, trader, instrument, stop_price):
        if self.stop_oid:
            # cancel the stop order and create a new one
            if trader.cancel_order(self.stop_oid):
                self.stop_ref_oid = None
                self.stop_oid = None
            else:
                return False

        if self.e == self.x:
            # all entry qty is filled
            return True

        if self.e < self.x:
            # something wrong but its ok
            return False

        if self.position_id:
            # if not accepted as modification do it as stop order
            if trader.modify_position(self.position_id, stop_loss_price=stop_price):
                self.sl = stop_price
                return True

        elif self.e > 0:
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

            if trader.create_order(order):  
                self.stop_oid = order.order_id
                self.stop_order_qty = order.quantity
                
                self.last_sl_ot[0] = order.created_time
                self.last_sl_ot[1] += 1

                self.sl = stop_price

                return True
            else:
                self.stop_ref_oid = None
                self.stop_order_qty = 0.0

        return False

    def close(self, trader, instrument):
        """
        Close the position and cancel the related orders.
        """
        if self._closing:
            # already closing order
            return False

        if self.create_oid:
            # cancel the remaining buy order
            if trader.cancel_order(self.create_oid):
                self.create_ref_oid = None
                self.create_oid = None

                self._entry_state = StrategyTrade.STATE_CANCELED

        if self.stop_oid:
            # cancel the stop order
            if trader.cancel_order(self.stop_oid):
                self.stop_ref_oid = None
                self.stop_oid = None

        if self.limit_oid:
            # cancel the limit order
            if trader.cancel_order(self.limit_oid):
                self.limit_ref_oid = None

        if self.position_id:
            # most of the margin broker case we have a position id
            if self._exit_state != StrategyTrade.STATE_PARTIALLY_FILLED:
                if trader.close_position(self.position_id):
                    return True
                else:
                    return False

        elif self.e - self.x > 0.0:
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

            if trader.create_order(order):
                self.stop_oid = order.order_id
                self.stop_order_qty = order.quantity

                # closing order defined
                self._closing = True

                return True
            else:
                self.stop_ref_oid = None
                return False

        return True

    def has_stop_order(self):
        return self.stop_oid is not None and self.stop_oid != ""

    def has_limit_order(self):
        return self.limit_oid is not None and self.limit_oid != ""

    def support_both_order(self):
        return True

    #
    # signal
    #

    def order_signal(self, signal_type, data, ref_order_id, instrument):
        if signal_type == Signal.SIGNAL_ORDER_OPENED:
            # already get at the return of create_order
            if ref_order_id == self.create_ref_oid:
                self.create_oid = data['id']

                # init created timestamp at the create order open
                self.eot = data['timestamp']

                if data.get('stop-loss'):
                    self.sl = data['stop-loss']

                if data.get('take-profit'):
                    self.tp = data['take-profit']

                self._entry_state = StrategyTrade.STATE_OPENED

            elif ref_order_id == self.stop_ref_oid:
                self.stop_oid = data['id']

                self.xot = data['timestamp']
                # self._exit_state = StrategyTrade.STATE_OPENED

            elif ref_order_id == self.limit_ref_oid:
                self.limit_oid = data['id']

                self.xot = data['timestamp']
                # self._exit_state = StrategyTrade.STATE_OPENED

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

                # logger.info("Entry avg-price=%s cum-filled=%s" % (self.aep, self.e))

                if self.e >= self.oq:
                    self._entry_state = StrategyTrade.STATE_FILLED

                    # bitmex does not send ORDER_DELETED signal, cleanup here
                    self.create_oid = None
                    self.create_ref_oid = None
                else:
                    self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED

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

    def position_signal(self, signal_type, data, ref_order_id, instrument):
        if signal_type == Signal.SIGNAL_POSITION_OPENED:
            self.position_id = data['id']

            # open position as created timestamp
            self.eot = data['timestamp']

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

            self.e += filled

            # logger.info("Entry avg-price=%s cum-filled=%s" % (self.aep, self.e))

            if self.e >= self.oq:
                self._entry_state = StrategyTrade.STATE_FILLED
            else:
                self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED

        elif signal_type == Signal.SIGNAL_POSITION_UPDATED:
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
                # increase/decrease profit/loss
                if self.dir > 0:
                    self.pl += ((data['exec-price'] * filled) - (self.aep * self.e)) / (self.aep * self.e)  # over entry executed quantity
                elif self.dir < 0:
                    self.pl += ((self.aep * self.e) - (data['exec-price'] * filled)) / (self.aep * self.e)  # over entry executed quantity

                # compute the average exit price
                self.axp = ((self.axp * self.x) + (data['exec-price'] * filled)) / (self.x + filled)

            # but this is in quote qty and we want in % change
            # if data.get('profit-loss') is not None:
            #     self.pl = data['profit-loss']

            self.x += filled

            logger.info("Exit avg-price=%s cum-filled=%s" % (self.axp, self.x))

            if self.x >= self.oq:
                self._exit_state = StrategyTrade.STATE_FILLED
            else:
                self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED

        elif signal_type == Signal.SIGNAL_POSITION_DELETED:
            # no longer related position
            self.position_id = None

            # it depends of the order of the position deleted...
            # @todo in some case not a good idea
            self.create_oid = None
            self.create_ref_oid = None

            if self.x < self.e:
                # mean fill the rest (positions are distincts)
                filled = self.e - self.x

                if data.get('exec-price') is not None and data['exec-price'] > 0:
                    # increase/decrease profit/loss (over entry executed quantity)
                    if self.dir > 0:
                        self.pl += ((data['exec-price'] * filled) - (self.aep * self.e)) / (self.aep * self.e)
                    elif self.dir < 0:
                        self.pl += ((self.aep * self.e) - (data['exec-price'] * filled)) / (self.aep * self.e)

                # but this is in quote qty and we want in % change
                # if data.get('profit-loss') is not None:
                #     self.pl = data['profit-loss']

                self.x += filled

                logger.info("Exit avg-price=%s cum-filled=%s" % (self.axp, self.x))

                self._exit_state = StrategyTrade.STATE_FILLED

        elif signal_type == Signal.SIGNAL_POSITION_AMENDED:
            # update stop_loss/take_profit from outside
            # @todo
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
    # persistance
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

    def loads(self, data, strategy_service):
        if not super().loads(data):
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
