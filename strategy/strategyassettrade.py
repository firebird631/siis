# @date 2018-12-28
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade for asset.

from notifier.signal import Signal
from database.database import Database

from trader.order import Order
from .strategytrade import StrategyTrade

import logging
logger = logging.getLogger('siis.strategy.assettrade')


class StrategyAssetTrade(StrategyTrade):
    """
    Specialization for asset buy/sell trading.
    Only an initial buy order, and a single, either a stop or a take-profit order.

    @todo fill the exit_trades and update the x and axp each time
    @todo for modify_sl/tp could use OCO order if avaible from market
    @todo support of OCO order
    """

    __slots__ = 'entry_ref_oid', 'stop_ref_oid', 'limit_ref_oid', 'oco_ref_oid', 'entry_oid', 'stop_oid', 'limit_oid', 'oco_oid', \
                'stop_order_type', 'stop_order_qty', 'limit_order_type', 'limit_order_qty', '_use_oco'

    def __init__(self, timeframe):
        super().__init__(StrategyTrade.TRADE_BUY_SELL, timeframe)

        self.entry_ref_oid = None
        self.stop_ref_oid = None
        self.limit_ref_oid = None
        self.oco_ref_oid = None

        self.entry_oid = None   # related entry buy order id
        self.stop_oid = None    # related exit sell stop order id
        self.limit_oid = None   # related exit sell limit order id
        self.oco_oid = None     # related exit sell OCO order id

        self.stop_order_type = Order.ORDER_MARKET
        self.stop_order_qty = 0.0

        self.limit_order_type = Order.ORDER_MARKET
        self.limit_order_qty = 0.0

    def open(self, trader, instrument, direction, order_type, order_price, quantity, take_profit, stop_loss, leverage=1.0, hedging=None, use_oco=False):
        """
        Buy an asset.
        """
        if self._entry_state != StrategyTrade.STATE_NEW:
            return False

        order = Order(trader, instrument.market_id)
        order.direction = direction
        order.price = order_price
        order.order_type = order_type
        order.quantity = quantity

        # generated a reference order id
        trader.set_ref_order_id(order)
        self.entry_ref_oid = order.ref_order_id

        self.dir = order.direction

        self.op = order.price     # retains the order price
        self.oq = order.quantity  # ordered quantity

        self.tp = take_profit
        self.sl = stop_loss

        self._use_oco = use_oco

        self._stats['entry-order-type'] = order.order_type

        if trader.create_order(order):
            if not self.eot and order.created_time:
                # only at the first open
                self.eot = order.created_time

            return True
        else:
            self._entry_state = StrategyTrade.STATE_REJECTED
            return False

    def remove(self, trader):
        if self.entry_oid:
            # cancel the remaining buy order
            if trader.cancel_order(self.entry_oid):
                # returns true, no need to wait signal confirmation
                self.entry_ref_oid = None
                self.entry_oid = None

                if self.e <= 0:
                    # no entry qty processed, entry canceled
                    self._entry_state = StrategyTrade.STATE_CANCELED
                else:
                    # cancel a partially filled trade means it is then fully filled
                    self._entry_state = StrategyTrade.STATE_FILLED

        if self.oco_oid:
            # cancel the oco sell order
            if trader.cancel_order(self.oco_oid):
                # returns true, no need to wait signal confirmation
                self.oco_ref_oid = None
                self.oco_oid = None
                self.stop_oid = None
                self.limit_oid = None

                if self.e <= 0 and self.x <= 0:
                    # no exit qty
                    self._exit_state = StrategyTrade.STATE_CANCELED
                elif self.x >= self.e:
                    self._exit_state = StrategyTrade.STATE_FILLED
                else:
                    self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED
        else:
            if self.stop_oid:
                # cancel the stop sell order
                if trader.cancel_order(self.stop_oid):
                    # returns true, no need to wait signal confirmation
                    self.stop_ref_oid = None
                    self.stop_oid = None

                    if self.e <= 0 and self.x <= 0:
                        # no exit qty
                        self._exit_state = StrategyTrade.STATE_CANCELED
                    elif self.x >= self.e:
                        self._exit_state = StrategyTrade.STATE_FILLED
                    else:
                        self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED

            if self.limit_oid:
                # cancel the sell limit order
                if trader.cancel_order(self.limit_oid):
                    # returns true, no need to wait signal confirmation
                    self.limit_ref_oid = None
                    self.limit_oid = None

                    if self.e <= 0 and self.x <= 0:
                        # no exit qty
                        self._exit_state = StrategyTrade.STATE_CANCELED
                    elif self.x >= self.e:
                        self._exit_state = StrategyTrade.STATE_FILLED
                    else:
                        self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED

    def cancel_open(self, trader):
        if self.entry_oid:
            # cancel the buy order
            if trader.cancel_order(self.entry_oid):
                # returns true, no need to wait signal confirmation
                self.entry_oid = None
                self.entry_ref_oid = None

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
        if self._closing:
            # already closing order
            return self.NOTHING_TO_DO

        if self._exit_state == StrategyTrade.STATE_FILLED:
            # exit already fully filled
            return self.NOTHING_TO_DO

        if self.oco_oid:
            # @todo need recreate stop and limit OCO order
            return self.ERROR
        else:
            if self.limit_oid:
                # cancel the sell limit order and create a new one
                if trader.cancel_order(self.limit_oid):
                    # REST sync
                    self.limit_ref_oid = None
                    self.limit_oid = None
                    self.limit_order_type = Order.ORDER_MARKET
                    self.limit_order_qty = 0.0
                else:
                    return self.ERROR

            if self.stop_oid:
                # cancel the sell stop order (only one or the other)
                if trader.cancel_order(self.stop_oid):
                    # REST sync
                    # returns true, no need to wait signal confirmation
                    self.stop_ref_oid = None
                    self.stop_oid = None
                    self.stop_order_type = Order.ORDER_MARKET
                    self.stop_order_qty = 0.0
                else:
                    return self.ERROR

            if self.x >= self.e:
                # all entry qty is filled
                return self.NOTHING_TO_DO

            if limit_price:
                order = Order(trader, instrument.market_id)
                order.direction = -self.dir  # neg dir
                order.order_type = Order.ORDER_LIMIT
                order.price = limit_price
                order.quantity = self.e - self.x  # remaining

                self._stats['limit-order-type'] = order.order_type

                # generated a reference order id
                trader.set_ref_order_id(order)
                self.limit_ref_oid = order.ref_order_id

                if trader.create_order(order):
                    # REST sync
                    self.limit_oid = order.order_id

                    self.limit_order_type = order.order_type
                    self.limit_order_qty = order.quantity

                    self.last_limit_ot[0] = order.created_time
                    self.last_limit_ot[1] += 1

                    self.tp = limit_price

                    return self.ACCEPTED
                else:
                    # rejected
                    self.limit_ref_oid = None
                    self.limit_order_qty = 0.0

                    return self.REJECTED

            return self.NOTHING_TO_DO

    def modify_stop_loss(self, trader, instrument, stop_price):
        if self._closing:
            # already closing order
            return self.NOTHING_TO_DO

        if self._exit_state == StrategyTrade.STATE_FILLED:
            # exit already fully filled
            return self.NOTHING_TO_DO

        if self.oco_oid:
            # @todo need recreate stop and limit OCO order
            return self.ERROR
        else:
            if self.stop_oid:
                # cancel the sell stop order and create a new one
                if trader.cancel_order(self.stop_oid):
                    # REST sync
                    # returns true, no need to wait signal confirmation
                    self.stop_ref_oid = None
                    self.stop_oid = None
                    self.stop_order_type = Order.ORDER_MARKET
                    self.stop_order_qty = 0.0
                else:
                    return self.ERROR

            if self.limit_oid:
                # cancel the sell limit order (only one or the other)
                if trader.cancel_order(self.limit_oid):
                    # REST sync
                    # returns true, no need to wait signal confirmation
                    self.limit_ref_oid = None
                    self.limit_oid = None
                    self.limit_order_type = Order.ORDER_MARKET
                    self.limit_order_qty = 0.0
                else:
                    return self.ERROR

            if self.x >= self.e:
                # all entry qty is filled
                return self.NOTHING_TO_DO

            if stop_price:
                order = Order(trader, instrument.market_id)
                order.direction = -self.dir  # neg dir
                order.order_type = Order.ORDER_STOP
                order.stop_price = stop_price
                order.quantity = self.e - self.x  # remaining

                self._stats['stop-order-type'] = order.order_type

                # generated a reference order id
                trader.set_ref_order_id(order)
                self.stop_ref_oid = order.ref_order_id

                if trader.create_order(order):
                    # REST sync
                    self.stop_oid = order.order_id

                    self.stop_order_type = order.order_type
                    self.stop_order_qty = order.quantity

                    self.last_stop_ot[0] = order.created_time
                    self.last_stop_ot[1] += 1

                    self.sl = stop_price

                    return self.ACCEPTED
                else:
                    # rejected
                    self.stop_ref_oid = None
                    self.stop_order_qty = 0.0

                    return self.REJECTED

            return self.NOTHING_TO_DO

    def modify_oco(self, trader, instrument, limit_price, stop_price):
        # @todo
        return self.REJECTED

    def close(self, trader, instrument):
        if self._closing:
            # already closing order
            return self.NOTHING_TO_DO

        if self.oco_oid:
            # @todo cancel OCO order and create an order market
            return self.ERROR
        else:
            if self.stop_ref_oid:
                logger.error("Trade %s has already ordered an exit !" % self.id)
                return self.NOTHING_TO_DO

            if self.entry_oid:
                # cancel the remaining buy order
                if trader.cancel_order(self.entry_oid):
                    self.entry_ref_oid = None
                    self.entry_oid = None
                else:
                    return self.ERROR

            if self.limit_oid:
                # cancel the sell limit order
                if trader.cancel_order(self.limit_oid):
                    self.limit_ref_oid = None
                    self.limit_oid = None
                    self.limit_order_type = Order.ORDER_MARKET
                    self.limit_order_qty = 0.0
                else:
                    return self.ERROR

            if self.stop_oid:
                # cancel the sell stop order and create a new one
                if trader.cancel_order(self.stop_oid):
                    self.stop_ref_oid = None
                    self.stop_oid = None
                    self.stop_order_type = Order.ORDER_MARKET
                    self.stop_order_qty = 0.0
                else:
                    return self.ERROR

            if self.x >= self.e:
                # all qty is filled
                return self.NOTHING_TO_DO

            order = Order(trader, instrument.market_id)
            order.direction = -self.dir  # neg dir
            order.order_type = Order.ORDER_MARKET
            order.quantity = self.e - self.x  # remaining qty

            self._stats['stop-order-type'] = order.order_type

            # generated a reference order id and keep it before ordering to retrieve its signals
            trader.set_ref_order_id(order)
            self.stop_ref_oid = order.ref_order_id

            if trader.create_order(order):
                # REST sync
                self.stop_oid = order.order_id

                self.stop_order_type = order.order_type
                self.stop_order_qty = order.quantity

                # closing order defined
                self._closing = True

                return self.ACCEPTED
            else:
                # rejected
                self.stop_ref_oid = None
                return self.REJECTED

        return self.NOTHING_TO_DO

    def has_stop_order(self):
        return self.stop_oid != None and self.stop_oid != ""

    def has_limit_order(self):
        return self.limit_oid != None and self.limit_oid != ""

    def has_oco_order(self):
        return self.oco_oid != None and self.oco_oid != ""

    def support_both_order(self):
        if self.has_oco_order():
            # only if an OCO order is defined
            return True
        else:
            return False

    @classmethod
    def is_margin(cls):
        return False

    @classmethod
    def is_spot(cls):
        return True

    #
    # signals
    #

    def update_dirty(self, trader, instrument):
        if self._dirty:
            done = True

            if self.has_oco_order():
                done = False
                # @todo
            else:
                if self.has_limit_order() and self.tp > 0.0:
                    if self.modify_take_profit(trader, instrument, self.tp) <= 0:
                        done = False

                if self.has_stop_order() and self.sl > 0.0:
                    if self.modify_stop_loss(trader, instrument, self.sl) <= 0:
                        done = False

            if done:
                # clean dirty flag if all the order have been updated
                self._dirty = False

    def is_target_order(self, order_id, ref_order_id):
        if order_id and (order_id == self.entry_oid or order_id == self.stop_oid or order_id == self.limit_oid or order_id == self.oco_oid):
            return True

        if ref_order_id and (ref_order_id == self.entry_ref_oid or ref_order_id == self.stop_ref_oid or ref_order_id == self.limit_ref_oid or ref_order_id == self.oco_ref_oid):
            return True

        return False

    def order_signal(self, signal_type, data, ref_order_id, instrument):
        if signal_type == Signal.SIGNAL_ORDER_OPENED:
            # already get at the return of create_order
            if ref_order_id == self.entry_ref_oid:
                self.entry_oid = data['id']
                self.entry_ref_oid = None

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
                self.stop_ref_oid = None

                if not self.xot:
                    self.xot = data['timestamp']

                self._exit_state = StrategyTrade.STATE_OPENED

            elif ref_order_id == self.limit_ref_oid:
                self.limit_oid = data['id']
                self.limit_ref_oid = None

                if not self.xot:
                    self.xot = data['timestamp']

                self._exit_state = StrategyTrade.STATE_OPENED

        elif signal_type == Signal.SIGNAL_ORDER_TRADED:
            # update the trade quantity
            if (data['id'] == self.entry_oid) and ('filled' in data or 'cumulative-filled' in data):
                # a single order for the entry, then its OK and prefered to uses cumulative-filled and avg-price
                # because precision comes from the broker
                if data.get('cumulative-filled') is not None and data['cumulative-filled'] > 0:
                    filled = data['cumulative-filled'] - self.e  # compute filled qty
                elif data.get('filled') is not None and data['filled'] > 0:
                    filled = data['filled']
                else:
                    filled = 0

                if data.get('avg-price') is not None and data['avg-price']:
                    # average entry price is directly given
                    self.aep = data['avg-price']

                elif (data.get('exec-price') is not None and data['exec-price']) and (filled > 0):
                    # compute the average entry price whe increasing the trade
                    self.aep = instrument.adjust_price(((self.aep * self.e) + (data['exec-price'] * filled)) / (self.e + filled))

                # cumulative filled entry qty
                if data.get('cumulative-filled') is not None:
                    self.e = data.get('cumulative-filled')
                elif filled > 0:
                    self.e = instrument.adjust_quantity(self.e + filled)

                if filled > 0:
                    # probably need to update exit orders
                    self._dirty = True

                if filled > 0 and self.e == 0:
                    # initial fill we count the commission fee
                    self._stats['entry-fees'] = instrument.maker_commission if data.get('maker', False) else instrument.taker_commission

                if self.e >= self.oq:
                    self._entry_state = StrategyTrade.STATE_FILLED
                else:
                    self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED

                #
                # fees/commissions
                #

                if (data.get('commission-asset', "") == instrument.base) and (data.get('commission-amount', 0) > 0):
                    # commission asset is itself, have to reduce it from filled, done after status determination because of the qty reduced by the fee
                    self.e = instrument.adjust_quantity(self.e - data.get('commission-amount', 0.0))

                # realized fees
                self._stats['entry-fees'] += filled * (instrument.maker_fee if data.get('maker', False) else instrument.taker_fee)

                # retains the trade timestamp
                if not self._stats['first-realized-entry-timestamp']:
                    self._stats['first-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                self._stats['last-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                #
                # filled mean also deleted
                #

                if data.get('fully-filled'):
                    self.entry_oid = None
                    self.entry_ref_oid = None

            elif (data['id'] == self.limit_oid or data['id'] == self.stop_oid) and ('filled' in data or 'cumulative-filled' in data):
                # @warning on the exit side, normal case will have a single order, but possibly to have a 
                # partial limit TP, plus remaining in market
                if data.get('filled') is not None and data['filled'] > 0:
                    filled = data['filled']
                elif data.get('cumulative-filled') is not None and data['cumulative-filled'] > 0:
                    filled = data['cumulative-filled'] - self.x  # compute filled qty
                else:
                    filled = 0

                if data.get('exec-price') is not None and data['exec-price'] and filled > 0:
                    # profit/loss when reducing the trade (over executed entry qty)
                    self.pl += ((data['exec-price'] * filled) - (self.aep * filled)) / (self.aep * self.e)

                    # average exit price
                    self.axp = instrument.adjust_price(((self.axp * self.x) + (data['exec-price'] * filled)) / (self.x + filled))

                # elif data.get('avg-price') is not None and data['avg-price']:
                #     # average price is directly given
                #     self.pl = ((data['avg-price'] * (self.x + filled)) - (self.aep * filled)) / (self.aep * self.e)

                #     # average exit price
                #     self.axp = data['avg-price']

                # cumulative filled exit qty
                # if data.get('cumulative-filled') is not None:
                #     self.x = data.get('cumulative-filled')
                # else:

                if filled > 0:
                    self.x = instrument.adjust_quantity(self.x + filled)

                if self._entry_state == StrategyTrade.STATE_FILLED:
                    if self.x >= self.e:
                        # entry fully filled, exit filled the entry qty => exit fully filled
                        self._exit_state = StrategyTrade.STATE_FILLED
                    else:
                        # some of the entry qty is not filled at this time
                        self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED
                else:
                    if self.entry_oid and self.e < self.oq:
                        # the entry part is not fully filled, the entry order still exists
                        self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED
                    else:
                        # there is no longer entry order, then we have fully filled the exit
                        self._exit_state = StrategyTrade.STATE_FILLED

                #
                # fees/commissions
                #

                # commission asset is asset, have to reduce it from filled
                if (data.get('commission-asset', "") == instrument.base) and (data.get('commission-amount', 0) > 0):
                    self.x = instrument.adjust_quantity(self.x - data.get('commission-amount', 0))

                # realized fees
                self._stats['exit-fees'] += filled * (instrument.maker_fee if data.get('maker', False) else instrument.taker_fee)
                
                # retains the trade timestamp
                if not self._stats['first-realized-exit-timestamp']:
                    self._stats['first-realized-exit-timestamp'] = data.get('timestamp', 0.0)

                self._stats['last-realized-exit-timestamp'] = data.get('timestamp', 0.0)

                #
                # filled mean also deleted
                #

                if data.get('fully-filled'):
                    
                    if data['id'] == self.limit_oid:
                        self.limit_oid = None
                        self.limit_ref_oid = None
                    elif data['id'] == self.stop_oid:
                        self.stop_oid = None
                        self.stop_ref_oid = None

        elif signal_type == Signal.SIGNAL_ORDER_UPDATED:
            # order price or qty modified
            # but its rarely possible
            pass

        elif signal_type == Signal.SIGNAL_ORDER_DELETED:
            # order is not longer active
            if data == self.entry_oid:
                self.entry_ref_oid = None
                self.entry_oid = None

                if self.e > 0:
                    # entry order deleted but some qty exists means entry is fully filled
                    self._entry_state = StrategyTrade.STATE_FILLED

            elif data == self.stop_oid:
                self.stop_ref_oid = None
                self.stop_oid = None

            elif data == self.limit_oid:
                self.limit_ref_oid = None
                self.limit_oid = None

        elif signal_type == Signal.SIGNAL_ORDER_REJECTED:
            # order is rejected
            if data == self.entry_ref_oid:
                self.entry_ref_oid = None
                self.entry_oid = None

                self._entry_state = StrategyTrade.STATE_REJECTED

            elif data == self.stop_ref_oid:
                self.stop_ref_oid = None
                self.stop_oid = None

            elif data == self.limit_ref_oid:
                self.limit_ref_oid = None
                self.limit_oid = None

        elif signal_type == Signal.SIGNAL_ORDER_CANCELED:
            # order is not longer active
            if data == self.entry_oid:
                self.entry_ref_oid = None
                self.entry_oid = None

                if self.e > 0:
                    # entry order canceled but some qty exists means entry is fully filled
                    self._entry_state = StrategyTrade.STATE_FILLED

            elif data == self.stop_oid:
                self.stop_ref_oid = None
                self.stop_oid = None

            elif data == self.limit_oid:
                self.limit_ref_oid = None
                self.limit_oid = None

    def dumps(self):
        data = super().dumps()

        data['entry-ref-oid'] = self.entry_ref_oid
        data['entry-oid'] = self.entry_oid

        data['stop-ref-oid'] = self.stop_ref_oid
        data['stop-oid'] = self.stop_oid

        data['limit-ref-oid'] = self.limit_ref_oid
        data['limit-oid'] = self.limit_oid

        data['oco-ref-oid'] = self.oco_ref_oid
        data['oco-oid'] = self.oco_oid

        data['stop-order-type'] = self.stop_order_type
        data['stop-order-qty'] = self.stop_order_qty

        data['limit-order-type'] = self.limit_order_type
        data['limit-order-qty'] = self.limit_order_qty

        return data

    def loads(self, data, strategy_service):
        if not super().loads(data):
            return False

        self.entry_ref_oid = data.get('entry-ref-oid', None)
        self.entry_oid = data.get('entry-oid', None)

        self.stop_ref_oid = data.get('stop-ref-oid', None)
        self.stop_ref_oid = data.get('stop-oid', None)

        self.limit_ref_oid = data.get('limit-ref-oid', None)
        self.limit_ref_oid = data.get('limit-oid', None)

        self.oco_ref_oid = data.get('oco-ref-oid', None)
        self.oco_ref_oid = data.get('oco-oid', None)

        self.stop_order_type = data.get('stop-order-type', Order.ORDER_MARKET)
        self.stop_order_qty = data.get('stop_order_qty', 0.0)

        self.limit_order_type = data.get('limit-order-type', Order.ORDER_MARKET)
        self.limit_order_qty = data.get('limit_order_qty', 0.0)

        return True
