# @date 2018-12-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade for margin with multiples positions.

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from trader.trader import Trader
    from instrument.instrument import Instrument
    from strategy.strategytrader import StrategyTrader
    from strategy.strategytradercontext import StrategyTraderContextBuilder

from common.signal import Signal
from trader.order import Order

from .strategytrade import StrategyTrade

import logging
logger = logging.getLogger('siis.strategy.margintrade')


class StrategyMarginTrade(StrategyTrade):
    """
    Specialization for margin trading. 

    This type of trade is related to margin trading market, allowing or not hedging, where there is a
    position identifier per trade, but generally in the same direction (no hedging).

    Works with crypto margin brokers (kraken...).

    @todo do we need like with asset trade an exit_trades list to compute the axp and x values, because
        if we use cumulative-filled and avg-price we have the same problem here too.
    @todo have to check about position_updated qty with direction maybe or take care to have trade signal and 
        distinct entry from exit
    @todo fees and commissions
    """

    __slots__ = 'create_ref_oid', 'stop_ref_oid', 'limit_ref_oid', 'create_oid', 'stop_oid', 'limit_oid', \
        'position_id', 'leverage', 'stop_order_qty', 'limit_order_qty'

    def __init__(self, timeframe: float):
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

    def open(self, trader: Trader, instrument: Instrument, direction: int, order_type: int,
             order_price: float, quantity: float, take_profit: float, stop_loss: float,
             leverage: float = 1.0, hedging: Optional[bool] = None) -> bool:
        """
        Open a position or buy an asset.
        """
        if self._entry_state != StrategyTrade.STATE_NEW:
            return False

        order = Order(trader, instrument.market_id)
        order.direction = direction
        order.price = order_price
        order.order_type = order_type
        order.quantity = quantity
        order.post_only = False
        order.margin_trade = True
        order.leverage = leverage

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
        self._stats['profit-loss-currency'] = instrument.settlement or instrument.quote

        if trader.create_order(order, instrument) > 0:
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

    def reopen(self, trader: Trader, instrument: Instrument, quantity: float) -> bool:
        if self._entry_state != StrategyTrade.STATE_CANCELED:
            return False

        # reset
        self._entry_state = StrategyTrade.STATE_NEW
        self.eot = 0.0

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

        if trader.create_order(order, instrument) > 0:
            self.create_oid = order.order_id
            self.position_id = order.position_id

            if not self.eot and order.created_time:
                # only at the first open
                self.eot = order.created_time

            return True
        else:
            self._entry_state = StrategyTrade.STATE_REJECTED
            return False

    def remove(self, trader: Trader, instrument: Instrument) -> int:
        """
        Remove the orders, but doesn't close the position.
        """
        error = False

        if self.create_oid:
            # cancel the remaining buy order
            if trader.cancel_order(self.create_oid, instrument) > 0:
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
            if trader.cancel_order(self.stop_oid, instrument) > 0:
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
            if trader.cancel_order(self.limit_oid, instrument) > 0:
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

    def cancel_open(self, trader: Trader, instrument: Instrument) -> int:
        if self.create_oid:
            # cancel the buy order
            if trader.cancel_order(self.create_oid, instrument) > 0:
                self.create_ref_oid = None
                self.create_oid = None

                if self.e <= 0:
                    # cancel a just opened trade means it is canceled
                    self._entry_state = StrategyTrade.STATE_CANCELED
                else:
                    # cancel a partially filled trade means it is then fully filled
                    self._entry_state = StrategyTrade.STATE_FILLED

                return self.ACCEPTED
            else:
                data = trader.order_info(self.create_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no create order, nothing to do
                    self.create_ref_oid = None
                    self.create_oid = None

                    self._entry_state = StrategyTrade.STATE_CANCELED
                else:
                    # exists, do nothing need to retry
                    return self.ERROR

        return self.NOTHING_TO_DO

    def modify_take_profit(self, trader: Trader, instrument: Instrument, limit_price: float, hard: bool = True) -> int:
        if self._closing:
            # already closing order
            return self.NOTHING_TO_DO

        if self._exit_state == StrategyTrade.STATE_FILLED:
            # exit already fully filled
            return self.NOTHING_TO_DO

        if self.limit_oid:
            # cancel the limit order and create a new one
            if trader.cancel_order(self.limit_oid, instrument) > 0:
                self.limit_ref_oid = None
                self.limit_oid = None
                self.limit_order_qty = 0.0
            else:
                data = trader.order_info(self.limit_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no limit order
                    self.limit_ref_oid = None
                    self.limit_oid = None
                    self.limit_order_qty = 0.0
                else:
                    return self.ERROR

        if self.x >= self.e:
            # all entry qty is filled, if lesser something wrong but its ok
            return self.NOTHING_TO_DO

        if limit_price and hard:
            # only if filled entry partially or totally
            order = Order(trader, instrument.market_id)
            order.direction = -self.direction
            order.order_type = Order.ORDER_LIMIT
            order.reduce_only = True
            order.quantity = self.e - self.x  # remaining
            order.price = limit_price
            order.margin_trade = True
            order.leverage = self.leverage

            trader.set_ref_order_id(order)
            self.limit_ref_oid = order.ref_order_id

            self._stats['take-profit-order-type'] = order.order_type

            create_order_result = trader.create_order(order, instrument)
            if create_order_result > 0:
                self.limit_oid = order.order_id
                self.limit_order_qty = order.quantity

                self.last_tp_ot[0] = order.created_time
                self.last_tp_ot[1] += 1

                self.tp = limit_price

                return self.ACCEPTED
            elif create_order_result == Order.REASON_INSUFFICIENT_MARGIN:
                # rejected because not enough margin, must stop to retry
                self.limit_ref_oid = None
                self.limit_order_qty = 0.0

                self._exit_state = self.STATE_ERROR

                return self.INSUFFICIENT_MARGIN
            else:
                self.limit_ref_oid = None
                self.limit_order_qty = 0.0

                return self.REJECTED
        elif limit_price:
            # soft take-profit
            self.tp = limit_price
        else:
            # remove take-profit
            self.tp = 0.0

        return self.NOTHING_TO_DO

    def modify_stop_loss(self, trader: Trader, instrument: Instrument, stop_price: float, hard: bool = True) -> int:
        if self._closing:
            # already closing order
            return self.NOTHING_TO_DO

        if self._exit_state == StrategyTrade.STATE_FILLED:
            # exit already fully filled
            return self.NOTHING_TO_DO

        if self.stop_oid:
            # cancel the stop order and create a new one
            if trader.cancel_order(self.stop_oid, instrument) > 0:
                self.stop_ref_oid = None
                self.stop_oid = None
                self.stop_order_qty = 0.0
            else:
                data = trader.order_info(self.stop_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no stop order
                    self.stop_ref_oid = None
                    self.stop_oid = None
                    self.stop_order_qty = 0.0
                else:
                    return self.ERROR

        if self.x >= self.e:
            # all entry qty is filled, if lesser something wrong but its ok
            return self.NOTHING_TO_DO

        if stop_price and hard:
            # only if filled entry partially or totally
            order = Order(trader, instrument.market_id)
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

            create_order_result = trader.create_order(order, instrument)
            if create_order_result > 0:
                self.stop_oid = order.order_id
                self.stop_order_qty = order.quantity

                self.last_stop_ot[0] = order.created_time
                self.last_stop_ot[1] += 1

                self.sl = stop_price

                return self.ACCEPTED
            elif create_order_result == Order.REASON_INSUFFICIENT_MARGIN:
                # rejected because not enough margin, must stop to retry
                self.stop_ref_oid = None
                self.stop_order_qty = 0.0

                self._exit_state = self.STATE_ERROR

                return self.INSUFFICIENT_MARGIN
            else:
                self.stop_ref_oid = None
                self.stop_order_qty = 0.0

                return self.REJECTED
        elif stop_price:
            # soft stop-loss
            self.sl = stop_price
        else:
            # remove stop-loss
            self.sl = 0.0

        return self.NOTHING_TO_DO

    def close(self, trader: Trader, instrument: Instrument) -> int:
        """
        Close the position and cancel the related orders.
        """
        if self._closing:
            # already closing order
            return self.NOTHING_TO_DO

        if self.create_oid:
            # cancel the remaining buy order
            if trader.cancel_order(self.create_oid, instrument) > 0:
                self.create_ref_oid = None
                self.create_oid = None

                self._entry_state = StrategyTrade.STATE_CANCELED
            else:
                data = trader.order_info(self.create_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no create order
                    self.create_ref_oid = None
                    self.create_oid = None
                else:
                    return self.ERROR

        if self.stop_oid:
            # cancel the stop order
            if trader.cancel_order(self.stop_oid, instrument) > 0:
                self.stop_ref_oid = None
                self.stop_oid = None
                self.stop_order_qty = 0.0
            else:
                data = trader.order_info(self.stop_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no stop order
                    self.stop_ref_oid = None
                    self.stop_oid = None
                    self.stop_order_qty = 0.0
                else:
                    return self.ERROR

        if self.limit_oid:
            # cancel the limit order
            if trader.cancel_order(self.limit_oid, instrument) > 0:
                self.limit_ref_oid = None
                self.limit_oid = None
                self.limit_order_qty = 0.0
            else:
                data = trader.order_info(self.limit_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no limit order
                    self.limit_ref_oid = None
                    self.limit_oid = None
                    self.limit_order_qty = 0.0
                else:
                    return self.ERROR

        if self.x >= self.e:
            # all qty is filled
            return self.NOTHING_TO_DO

        order = Order(trader, instrument.market_id)
        order.direction = -self.dir  # neg dir
        order.order_type = Order.ORDER_MARKET
        order.reduce_only = True
        order.quantity = self.e - self.x  # remaining qty
        order.margin_trade = True
        order.leverage = self.leverage

        # generated a reference order id
        trader.set_ref_order_id(order)
        self.stop_ref_oid = order.ref_order_id

        self._stats['stop-order-type'] = order.order_type

        create_order_result = trader.create_order(order, instrument)
        if create_order_result > 0:
            self.stop_oid = order.order_id
            self.stop_order_qty = order.quantity

            # closing order defined
            self._closing = True

            return self.ACCEPTED
        elif create_order_result == Order.REASON_INSUFFICIENT_MARGIN:
            # rejected because not enough margin, must stop to retry
            self.stop_ref_oid = None
            self.stop_order_qty = 0.0

            self._exit_state = self.STATE_ERROR

            return self.INSUFFICIENT_MARGIN
        else:
            self.stop_ref_oid = None
            self.stop_order_qty = 0.0

            return self.REJECTED

    def has_stop_order(self) -> bool:
        return self.stop_oid is not None and self.stop_oid != ""

    def has_limit_order(self) -> bool:
        return self.limit_oid is not None and self.limit_oid != ""

    def support_both_order(self) -> bool:
        return True

    @classmethod
    def is_margin(cls) -> bool:
        return True

    @classmethod
    def is_spot(cls) -> bool:
        return False

    @property
    def invested_quantity(self) -> float:
        if self.is_active():
            return self.e - self.x
        elif self.op:
            return self.oq
        else:
            return 0.0

    #
    # signal
    #

    def order_signal(self, signal_type: int, data: dict, ref_order_id: str, instrument: Instrument):
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

                if self.e == 0:  # in case it occurs after position open signal
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
                prev_e = self.e

                # a single order for the entry, then its OK and preferred to uses cumulative-filled and avg-price
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

                    # if no send of ORDER_DELETED signal, cleanup here
                    self.create_oid = None
                    self.create_ref_oid = None
                else:
                    self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED

                # retains the trade timestamp
                if not self._stats['first-realized-entry-timestamp']:
                    self._stats['first-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                self._stats['last-realized-entry-timestamp'] = data.get('timestamp', 0.0)

            elif data['id'] == self.limit_oid or data['id'] == self.stop_oid:
                prev_x = self.x

                # either we have 'filled' component (partial qty) or the 'cumulative-filled' or both
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

                    # if no send of ORDER_DELETED signal, cleanup here
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

    def position_signal(self, signal_type: int, data: dict, ref_order_id: str, instrument: Instrument):
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
            # might not occur
            pass

    def is_target_order(self, order_id: str, ref_order_id: str) -> bool:
        if order_id and (order_id == self.create_oid or order_id == self.stop_oid or order_id == self.limit_oid):
            return True

        if ref_order_id and (ref_order_id == self.create_ref_oid or
                             ref_order_id == self.stop_ref_oid or
                             ref_order_id == self.limit_ref_oid):
            return True

        return False

    def is_target_position(self, position_id: str, ref_order_id: str) -> bool:
        if position_id and (position_id == self.position_id):
            return True

        if ref_order_id and (ref_order_id == self.create_ref_oid):
            return True

    #
    # persistence
    #

    def dumps(self) -> dict:
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

    def loads(self, data: dict, strategy_trader: StrategyTrader,
              context_builder: Optional[StrategyTraderContextBuilder] = None) -> bool:
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

    def check(self, trader: Trader, instrument: Instrument) -> int:
        result = 1

        #
        # entry
        #

        if self.create_oid:
            data = trader.order_info(self.create_oid, instrument)

            if data is None:
                # API error, do nothing need retry
                result = -1

                # entry order error status
                # self._entry_state = StrategyTrade.STATE_ERROR
            else:
                if data['id'] is None:
                    # cannot retrieve the order, wrong id
                    result = 0

                    # no longer entry order
                    self.create_oid = None
                    self.create_ref_oid = None
                else:
                    if data['cumulative-filled'] > self.e or data['fully-filled']:
                        self.order_signal(Signal.SIGNAL_ORDER_TRADED, data, data['ref-id'], instrument)

                    if data['status'] in ('closed', 'deleted'):
                        self.order_signal(Signal.SIGNAL_ORDER_DELETED, data['id'], data['ref-id'], instrument)

                    elif data['status'] in ('expired', 'canceled'):
                        self.order_signal(Signal.SIGNAL_ORDER_CANCELED, data['id'], data['ref-id'], instrument)

        #
        # exit
        #

        if self.stop_oid:
            data = trader.order_info(self.stop_oid, instrument)

            if data is None:
                # API error, do nothing need retry
                result = -1

                # exit order error status
                # self._exit_state = StrategyTrade.STATE_ERROR
            else:
                if data['id'] is None:
                    # cannot retrieve the order, wrong id
                    result = 0

                    # no longer stop order
                    self.stop_oid = None
                    self.stop_ref_oid = None
                else:
                    if data['cumulative-filled'] > self.x or data['fully-filled']:
                        self.order_signal(Signal.SIGNAL_ORDER_TRADED, data, data['ref-id'], instrument)

                    if data['status'] in ('closed', 'deleted'):
                        self.order_signal(Signal.SIGNAL_ORDER_DELETED, data['id'], data['ref-id'], instrument)

                    elif data['status'] in ('expired', 'canceled'):
                        self.order_signal(Signal.SIGNAL_ORDER_CANCELED, data['id'], data['ref-id'], instrument)

        if self.limit_oid:
            data = trader.order_info(self.limit_oid, instrument)

            if data is None:
                # API error, do nothing need retry
                result = -1

                # exit order error status
                # self._exit_state = StrategyTrade.STATE_ERROR
            else:
                if data['id'] is None:
                    # cannot retrieve the order, wrong id
                    result = 0

                    # no longer stop order
                    self.limit_oid = None
                    self.limit_ref_oid = None
                else:
                    if data['cumulative-filled'] > self.x or data['fully-filled']:
                        self.order_signal(Signal.SIGNAL_ORDER_TRADED, data, data['ref-id'], instrument)

                    if data['status'] in ('closed', 'deleted'):
                        self.order_signal(Signal.SIGNAL_ORDER_DELETED, data['id'], data['ref-id'], instrument)

                    elif data['status'] in ('expired', 'canceled'):
                        self.order_signal(Signal.SIGNAL_ORDER_CANCELED, data['id'], data['ref-id'], instrument)

        return result

    def repair(self, trader: Trader, instrument: Instrument) -> bool:
        # @todo fix the trade

        return False

    #
    # stats
    #

    def update_stats(self, instrument: Instrument, timestamp: float):
        super().update_stats(instrument, timestamp)

        if self.is_active():
            # @todo support only for quantity in asset not in lot or contract of different size
            last_price = instrument.close_exec_price(self.direction)

            upnl = 0.0  # unrealized PNL
            rpnl = 0.0  # realized PNL

            # non realized quantity
            nrq = self.e - self.x

            if self.dir > 0:
                upnl = (last_price - self.aep) * nrq * instrument.contract_size
                rpnl = (self.axp - self.aep) * self.x * instrument.contract_size
            elif self.dir < 0:
                upnl = (self.aep - last_price) * nrq * instrument.contract_size
                rpnl = (self.aep - self.axp) * self.x * instrument.contract_size

            # including fees and realized profit and loss
            self._stats['unrealized-profit-loss'] = instrument.adjust_quote(
                upnl + rpnl - self._stats['entry-fees'] - self._stats['exit-fees'])

    def info_report(self, strategy_trader: StrategyTrader) -> Tuple[str]:
        data = list(super().info_report(strategy_trader))

        if self.create_oid or self.create_ref_oid:
            data.append("Entry order id / ref : %s / %s" % (self.create_oid, self.create_ref_oid))

        if self.stop_oid or self.stop_ref_oid:
            data.append("Stop order id / ref : %s / %s" % (self.stop_oid, self.stop_ref_oid))

        if self.limit_oid or self.limit_ref_oid:
            data.append("Limit order id / ref : %s / %s" % (self.limit_oid, self.limit_ref_oid))

        if self.position_id:
            data.append("Position id : %s" % (self.position_id,))

        return tuple(data)
