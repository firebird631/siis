# @date 2018-12-28
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade for margin individual position

from common.signal import Signal
from database.database import Database

from trader.order import Order
from .strategytrade import StrategyTrade

import logging
logger = logging.getLogger('siis.strategy.positiontrade')


class StrategyPositionTrade(StrategyTrade):
    """
    Specialization for margin individual position trading. 

    This type of trade is related to margin trading market, allowing hedging.
    Works with CFD brokers (ig...).
    """

    __slots__ = 'create_ref_oid', 'create_oid', 'position_id', 'position_stop', 'position_limit', 'position_quantity', 'leverage'

    def __init__(self, timeframe):
        super().__init__(StrategyTrade.TRADE_POSITION, timeframe)

        self.create_ref_oid = None

        self.create_oid = None   # related entry order id
        self.position_id = None  # related position id

        self.position_stop = 0.0      # Non zero mean position had a stop defined on broker side
        self.position_limit = 0.0     # Non zero mean position had a limit defined on broker side
        self.position_quantity = 0.0  # Current position quantity

        self.leverage = 1.0

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
            self.create_oid = order.order_id
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

                if self.e <= 0:
                    # no entry qty processed, entry canceled
                    self._entry_state = StrategyTrade.STATE_CANCELED
                else:
                    # cancel a partially filled trade means it is then fully filled
                    self._entry_state = StrategyTrade.STATE_FILLED

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
        if self.position_id:
            # if not accepted as modification do it as limit order
            if trader.modify_position(self.position_id, take_profit_price=limit_price):
                self.tp = limit_price
                self.position_limit = limit_price
                return self.ACCEPTED
            else:
                return self.REJECTED

        return self.NOTHING_TO_DO

    def modify_stop_loss(self, trader, instrument, stop_price):
        if self.position_id:
            # if not accepted as modification do it as stop order
            if trader.modify_position(self.position_id, stop_loss_price=stop_price):
                self.sl = stop_price
                self.position_stop = stop_price
                return self.ACCEPTED
            else:
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
            if trader.cancel_order(self.create_oid):
                self.create_ref_oid = None
                self.create_oid = None

                self._entry_state = StrategyTrade.STATE_CANCELED

        if self.position_id:
            # most of the margin broker case we have a position id
            if trader.close_position(self.position_id):
                self._closing = True
                return self.ACCEPTED
            else:
                return self.REJECTED

        return self.NOTHING_TO_DO

    def has_stop_order(self):
        return self.position_stop > 0.0

    def has_limit_order(self):
        return self.position_limit > 0.0

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

                if self.e == 0:
                    # because could occurs after position open signal
                    self._entry_state = StrategyTrade.STATE_OPENED

        elif signal_type == Signal.SIGNAL_ORDER_DELETED:
            # order is no longer active
            if data == self.create_oid:
                self.create_ref_oid = None                
                self.create_oid = None

                if not self.position_id:
                    self._entry_state = StrategyTrade.STATE_DELETED

        elif signal_type == Signal.SIGNAL_ORDER_CANCELED:
            # order is no longer active
            if data == self.create_oid:
                self.create_ref_oid = None                
                self.create_oid = None

                if not self.position_id:
                    self._entry_state = StrategyTrade.STATE_CANCELED

        elif signal_type == Signal.SIGNAL_ORDER_UPDATED:
            # order price/qty modified, cannot really be used because the strategy might
            # cancel the trade or create another one.
            # for the qty we could have a remaining_qty member, then comparing
            pass

        elif signal_type == Signal.SIGNAL_ORDER_TRADED:
            # order fully or partially filled
            filled = 0

            if (data['id'] == self.create_oid or data['id'] == self.position_id):
                info = data.get('info', "")

                # if info == "closed" or info == "partially-closed":
                #     print(data)

                # if data.get('cumulative-filled') is not None and data['cumulative-filled'] > 0:
                #     filled = data['cumulative-filled'] - self.e  # compute filled qty
                # elif data.get('filled') is not None and data['filled'] > 0:
                #     filled = data['filled']
                # else:
                #     filled = 0

                # if data.get('avg-price') is not None and data['avg-price'] > 0:
                #     # in that case we have avg-price already computed
                #     self.aep = data['avg-price']

                # elif data.get('exec-price') is not None and data['exec-price'] > 0:
                #     # compute the average price
                #     self.aep = ((self.aep * self.e) + (data['exec-price'] * filled)) / (self.e + filled)
                # else:
                #     # no have uses order price
                #     self.aep = self.op

                # # cumulative filled entry qty
                # if data.get('cumulative-filled') is not None:
                #     self.e = data.get('cumulative-filled')
                # elif filled > 0:
                #     self.e = instrument.adjust_quantity(self.e + filled)

                # if filled > 0:
                #     # probably need to update exit orders
                #     self._dirty = True

                # logger.info("Entry avg-price=%s cum-filled=%s" % (self.aep, self.e))

                # if self.e >= self.oq:
                #     self._entry_state = StrategyTrade.STATE_FILLED

                #     # bitmex does not send ORDER_DELETED signal, cleanup here
                #     self.create_oid = None
                #     self.create_ref_oid = None
                # else:
                #     self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED

                # # retains the trade timestamp
                # if not self._stats['first-realized-entry-timestamp']:
                #     self._stats['first-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                # self._stats['last-realized-entry-timestamp'] = data.get('timestamp', 0.0)

            if data.get('profit-loss'):
                self._stats['unrealized-profit-loss'] = data['profit-loss']
            if data.get('profit-currency'):
                self._stats['profit-loss-currency'] = data['profit-currency']

    def position_signal(self, signal_type, data, ref_order_id, instrument):
        if signal_type == Signal.SIGNAL_POSITION_OPENED:
            self.position_id = data['id']

            if data.get('profit-loss'):
                self._stats['unrealized-profit-loss'] = data['profit-loss']
            if data.get('profit-currency'):
                self._stats['profit-loss-currency'] = data['profit-currency']

            if data.get('take-profit'):
                self.position_limit = data['take-profit']

            if data.get('stop-loss'):
                self.position_limit = data['stop-loss']

            if not self.xot and (data.get('take-profit') or data.get('stop-loss')):
                self.xot = data['timestamp']

            last_qty = data.get('quantity', 0.0)

            if last_qty > 0.0:
                # increase entry
                self._stats['last-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                # filled entry quantity from the diff with the previous one
                self.e += last_qty - self.position_quantity

                if last_qty < self.oq:
                    self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED
                if last_qty >= self.oq:
                    self._entry_state = StrategyTrade.STATE_FILLED

            # retains the trade timestamp
            self._stats['first-realized-entry-timestamp'] = data.get('timestamp', 0.0)

        elif signal_type == Signal.SIGNAL_POSITION_UPDATED:
            # update the unrealized profit-loss in currency
            if data.get('profit-loss'):
                self._stats['unrealized-profit-loss'] = data['profit-loss']
            if data.get('profit-currency'):
                self._stats['profit-loss-currency'] = data['profit-currency']

            if data.get('take-profit'):
                self.position_limit = data['take-profit']

            if data.get('stop-loss'):
                self.position_limit = data['stop-loss']

            last_qty = data.get('quantity', 0.0)

            if self.position_quantity != last_qty:
                if last_qty < self.position_quantity:
                    # decrease mean exit
                    if not self._stats['first-realized-exit-timestamp']:
                        self._stats['first-realized-exit-timestamp'] = data.get('timestamp', 0.0)

                    self._stats['last-realized-exit-timestamp'] = data.get('timestamp', 0.0)

                    # filled entry quantity from the diff with the previous one
                    self.x += self.position_quantity - last_qty

                    if last_qty > 0.0:
                        self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED
                    if last_qty <= 0.0:
                        self._exit_state = StrategyTrade.STATE_FILLED

                elif last_qty > self.position_quantity:
                    # increase mean entry
                    self._stats['last-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                    # filled entry quantity from the diff with the previous one
                    self.e += last_qty - self.position_quantity

                    if last_qty < self.oq:
                        self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED
                    if last_qty >= self.oq:
                        self._entry_state = StrategyTrade.STATE_FILLED

        elif signal_type == Signal.SIGNAL_POSITION_DELETED:
            # no longer related position
            self.position_id = None

            if data.get('profit-loss'):
                self._stats['unrealized-profit-loss'] = data['profit-loss']
            if data.get('profit-currency'):
                self._stats['profit-loss-currency'] = data['profit-currency']

            self.position_quantity = 0.0
            self._exit_state = StrategyTrade.STATE_FILLED

            # retains the last trade timestamp
            self._stats['last-realized-exit-timestamp'] = data.get('timestamp', 0.0)
            # logger.info("Exit avg-price=%s cum-filled=%s" % (self.axp, self.x))

        elif signal_type == Signal.SIGNAL_POSITION_AMENDED:
            # update stop_loss/take_profit from outside
            # @todo update position_stop and position_limit
            if data.get('profit-loss'):
                self._stats['unrealized-profit-loss'] = data['profit-loss']
            if data.get('profit-currency'):
                self._stats['profit-loss-currency'] = data['profit-currency']

            if data.get('take-profit'):
                self.position_limit = data['take-profit']

            if data.get('stop-loss'):
                self.position_limit = data['stop-loss']

            last_qty = data.get('quantity', 0.0)

            if self.position_quantity != last_qty:
                if last_qty < self.position_quantity:
                    # decrease mean exit
                    if not self._stats['first-realized-exit-timestamp']:
                        self._stats['first-realized-exit-timestamp'] = data.get('timestamp', 0.0)

                    self._stats['last-realized-exit-timestamp'] = data.get('timestamp', 0.0)

                    # filled entry quantity from the diff with the previous one
                    self.x += self.position_quantity - last_qty

                    if last_qty > 0.0:
                        self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED
                    if last_qty <= 0.0:
                        self._exit_state = StrategyTrade.STATE_FILLED

                elif last_qty > self.position_quantity:
                    # increase mean entry
                    self._stats['last-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                    # filled entry quantity from the diff with the previous one
                    self.e += last_qty - self.position_quantity

                    if last_qty < self.oq:
                        self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED
                    if last_qty >= self.oq:
                        self._entry_state = StrategyTrade.STATE_FILLED

                self.position_quantity = last_qty

        if data.get('profit'):
            self._stats['unrealized-profit-loss'] = data['profit']
        if data.get('profit-currency'):
            self._stats['profit-loss-currency'] = data['profit-currency']

        #
        # average entry/exit prices
        #

        if data.get('avg-entry-price'):
            self.aep = data['avg-entry-price']
        if data.get('avg-exit-price'):
            self.axp = data['avg-exit-price']

        #
        # profit/loss rate
        #

        if self.direction > 0:
            if self.aep > 0 and self.axp > 0:
                self.pl = (self.axp - self.aep) / self.aep
            elif self.aep > 0 and instrument.close_exec_price(1) > 0:
                self.pl = (instrument.close_exec_price(1) - self.aep) / self.aep
        elif self.direction < 0:
            if self.aep > 0 and self.axp > 0:
                self.pl = (self.aep - self.axp) / self.aep
            elif self.aep > 0 and instrument.close_exec_price(-1) > 0:
                self.pl = (self.aep - instrument.close_exec_price(-1)) / self.aep

    def is_target_order(self, order_id, ref_order_id):
        if order_id and (order_id == self.create_oid):
            return True

        if ref_order_id and (ref_order_id == self.create_ref_oid):
            return True

        return False

    def is_target_position(self, position_id, ref_order_id):
        if position_id and (position_id == self.position_id):
            return True

        if ref_order_id and (ref_order_id == self.create_ref_oid):
            return True

        return False

    #
    # persistance
    #

    def dumps(self):
        data = super().dumps()

        data['create-ref-oid'] = self.create_ref_oid
        data['create-oid'] = self.create_oid

        data['position-id'] = self.position_id
        data['position-stop'] = self.position_stop
        data['position-limit'] = self.position_limit

        return data

    def loads(self, data, strategy_service):
        if not super().loads(data):
            return False

        self.create_ref_oid = data.get('create-ref-oid')
        self.create_oid = data.get('create-oid')

        self.position_id = data.get('position-id')
        self.position_stop = data.get('position-stop')
        self.position_limit = data.get('position-limit')

        return True
