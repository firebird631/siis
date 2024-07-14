# @date 2018-12-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade for margin with an indivisible (unique) position.

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from trader.trader import Trader
    from instrument.instrument import Instrument
    from strategy.strategytraderbase import StrategyTraderBase

from common.signal import Signal
from trader.order import Order

from .strategytrade import StrategyTrade

import logging
logger = logging.getLogger('siis.strategy.indmargintrade')
error_logger = logging.getLogger('siis.error.strategy.indmargintrade')


class StrategyIndMarginTrade(StrategyTrade):
    """
    Specialization for indivisible margin position trade. Some exchanges allow two sides (case of binancesfutures),
    meaning in to different positions with the same symbol.

    In this case we only have a single position per market without integrated stop/limit.
    Works with crypto futures exchanges (bitmex, binancefutures, bybit, ftx...).

    We cannot deal in opposite direction at the same time (no hedging), but we can eventually manage many
    trades on the same direction.
    But with some exchanges (binancefutures) if the hedge mode is active it is possible to manage the both directions,
    through two different positions.

    We prefers here to update on trade order signal. A position deleted means to close any related orders.

    @todo position maintenance funding fees, but how to ?
    @todo support of two directional (hedging mode) positions (having a prefix or suffix on trader symbol)
    @todo in case if position closed externally it is necessary to update exit qty/price/fees and update then rpnl
    """

    __slots__ = 'create_ref_oid', 'stop_ref_oid', 'limit_ref_oid', \
                'create_oid', 'stop_oid', 'limit_oid', \
                'position_id', 'leverage', \
                'stop_order_qty', 'limit_order_qty', \
                'stop_order_exec', 'limit_order_exec', \
                'stop_order_cum_fees', 'limit_order_cum_fees'

    def __init__(self, timeframe: float):
        super().__init__(StrategyTrade.TRADE_IND_MARGIN, timeframe)

        self.create_ref_oid = None
        self.stop_ref_oid = None
        self.limit_ref_oid = None

        self.create_oid = None      # related entry order id
        self.stop_oid = None        # related stop order id
        self.limit_oid = None       # related limit order id

        self.position_id = None  # related position id
        self.leverage = 1.0

        self.stop_order_qty = 0.0        # ordered quantity of the current stop order
        self.limit_order_qty = 0.0       # ordered quantity of the current limit order

        self.stop_order_exec = 0.0        # executed quantity of the current stop order
        self.limit_order_exec = 0.0       # executed quantity of the current limit order

        self.stop_order_cum_fees = 0.0    # cumulative fees quantity of the current stop order
        self.limit_order_cum_fees = 0.0   # cumulative fees quantity of the current limit order

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
            self.position_id = order.position_id  # might be market-id, but it is related by hedging state

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
            self.position_id = order.position_id  # might be market-id, but related by hedging state

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
                # check create_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_create(trader, instrument)

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
                # check stop_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_stop(trader, instrument)

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
                # check limit_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_limit(trader, instrument)

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
                # check create_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_create(trader, instrument)

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
                    self.__reset_create()
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
                # check limit_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_limit(trader, instrument)
            else:
                data = trader.order_info(self.limit_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no limit order
                    self.__reset_limit()
                else:
                    return self.ERROR

        if self.x >= self.e:
            # all entry qty is filled, if lesser something wrong, but it is ok
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

            self._stats['take-profit-order-type'] = order.order_type

            # generated a reference order id
            trader.set_ref_order_id(order)

            # set before in case of async signal comes before
            self.limit_ref_oid = order.ref_order_id
            self.limit_order_qty = order.quantity
            self.limit_order_exec = 0.0
            self.limit_order_cum_fees = 0.0

            create_order_result = trader.create_order(order, instrument)
            if create_order_result > 0:
                self.limit_oid = order.order_id

                self.last_tp_ot[0] = order.created_time
                self.last_tp_ot[1] += 1

                self.tp = limit_price

                return self.ACCEPTED
            elif create_order_result == Order.REASON_INSUFFICIENT_MARGIN:
                # rejected because not enough margin, must stop to retry
                self.__reset_limit()
                self._exit_state = self.STATE_ERROR

                return self.INSUFFICIENT_MARGIN
            else:
                self.__reset_limit()
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
                # check stop_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_stop(trader, instrument)
            else:
                data = trader.order_info(self.stop_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no stop order
                    self.__reset_stop()
                else:
                    return self.ERROR

        if self.x >= self.e:
            # all entry qty is filled, if lesser something wrong, but it is ok
            return self.NOTHING_TO_DO

        if stop_price and hard:
            # only if filled entry partially or totally
            order = Order(trader, instrument.market_id)
            order.direction = -self.direction
            order.order_type = Order.ORDER_STOP
            order.reduce_only = True
            order.quantity = self.e - self.x  # remaining
            order.stop_price = stop_price
            order.margin_trade = True
            order.leverage = self.leverage

            self._stats['stop-order-type'] = order.order_type

            # generated a reference order id
            trader.set_ref_order_id(order)

            # set before in case of async signal comes before
            self.stop_ref_oid = order.ref_order_id
            self.stop_order_qty = order.quantity
            self.stop_order_exec = 0.0
            self.stop_order_cum_fees = 0.0

            create_order_result = trader.create_order(order, instrument)
            if create_order_result > 0:
                self.stop_oid = order.order_id

                self.last_stop_ot[0] = order.created_time
                self.last_stop_ot[1] += 1

                self.sl = stop_price

                return self.ACCEPTED
            elif create_order_result == Order.REASON_INSUFFICIENT_MARGIN:
                # rejected because not enough margin, must stop to retry
                self.__reset_stop()
                self._exit_state = self.STATE_ERROR

                return self.INSUFFICIENT_MARGIN
            else:
                self.__reset_stop()
                return self.REJECTED
        elif stop_price:
            # soft stop-loss
            self.sl = stop_price
        else:
            # remove stop-loss
            self.sl = 0.0

        return self.NOTHING_TO_DO

    def close(self, trader: Trader, instrument: Instrument) -> int:
        if self._closing:
            # already closing order
            return self.NOTHING_TO_DO

        if self.create_oid:
            # cancel the remaining buy order
            if trader.cancel_order(self.create_oid, instrument) > 0:
                # check create_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_create(trader, instrument)

                if self.e <= 0:
                    # only if non realized entry qty
                    self._entry_state = StrategyTrade.STATE_CANCELED
            else:
                data = trader.order_info(self.create_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no create order
                    self.__reset_create()
                else:
                    return self.ERROR

        if self.stop_oid:
            # cancel the stop order
            if trader.cancel_order(self.stop_oid, instrument) > 0:
                # check stop_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_stop(trader, instrument)
            else:
                data = trader.order_info(self.stop_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no stop order
                    self.__reset_stop()
                else:
                    return self.ERROR

        if self.limit_oid:
            # cancel the limit order
            if trader.cancel_order(self.limit_oid, instrument) > 0:
                # check limit_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_limit(trader, instrument)
            else:
                data = trader.order_info(self.limit_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no limit order
                    self.__reset_limit()
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

        self._stats['stop-order-type'] = order.order_type

        # generated a reference order id
        trader.set_ref_order_id(order)

        # set before in case of async signal comes before
        self.stop_ref_oid = order.ref_order_id
        self.stop_order_qty = order.quantity
        self.stop_order_exec = 0.0
        self.stop_order_cum_fees = 0.0

        create_order_result = trader.create_order(order, instrument)
        if create_order_result > 0:
            self.stop_oid = order.order_id

            # closing order defined
            self._closing = True

            return self.ACCEPTED
        elif create_order_result == Order.REASON_INSUFFICIENT_MARGIN:
            # rejected because not enough margin, must stop to retry
            self.__reset_stop()
            self._exit_state = self.STATE_ERROR

            return self.INSUFFICIENT_MARGIN
        else:
            self.__reset_stop()
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
    # signals
    #

    def update_dirty(self, trader: Trader, instrument: Instrument):
        # result invalid done only on error, but previously it was also invalided by a nothing to do.
        if self._dirty:
            done = True

            try:
                if self.has_limit_order() and self.tp > 0.0:
                    result = self.modify_take_profit(trader, instrument, self.tp, True)
                    if result < 0:
                        done = False

                if self.has_stop_order() and self.sl > 0.0:
                    result = self.modify_stop_loss(trader, instrument, self.sl, True)
                    if result < 0:
                        done = False

            except Exception as e:
                error_logger.error(str(e))
                return

            if done:
                # clean dirty flag if all the order have been updated
                self._dirty = False

    def order_signal(self, signal_type: int, data: dict, ref_order_id: str, instrument: Instrument):
        if signal_type == Signal.SIGNAL_ORDER_OPENED:
            if ref_order_id:
                if ref_order_id == self.create_ref_oid:
                    # might already get at the return of create_order
                    self.create_oid = data['id']

                    # init created timestamp at the create order open
                    if not self.eot:
                        self.eot = data['timestamp']

                    # but might not have stop-loss neither take-profit for this type of trade
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
            if data:
                if data == self.create_oid:
                    self.__reset_create()

                    if self.e <= 0:
                        # entry state as deleted only if non (or partially) filled
                        self._entry_state = StrategyTrade.STATE_DELETED

                elif data == self.limit_oid:
                    self.__reset_limit()

                elif data == self.stop_oid:
                    self.__reset_stop()

        elif signal_type == Signal.SIGNAL_ORDER_CANCELED:
            # order is no longer active
            if data:
                if data == self.create_oid:
                    self.__reset_create()

                    if self.e <= 0:
                        # entry state as canceled only if non (or partially) filled
                        self._entry_state = StrategyTrade.STATE_CANCELED

                elif data == self.limit_oid:
                    self.__reset_limit()

                elif data == self.stop_oid:
                    self.__reset_stop()

        elif signal_type == Signal.SIGNAL_ORDER_UPDATED:
            # order price/qty modified, cannot really be used because the strategy might
            # cancel the trade or create another one.
            # for the qty we could have a remaining_qty member, then comparing
            pass

        elif signal_type == Signal.SIGNAL_ORDER_TRADED:
            # update the trade quantity
            if 'filled' not in data and 'cumulative-filled' not in data:
                return

            def update_exit_qty(order_exec):
                """
                Inner function to update the exit qty.
                """
                # either we have 'filled' component (partial qty) or the 'cumulative-filled' or both
                if data.get('cumulative-filled') is not None and data['cumulative-filled'] > order_exec:
                    # compute filled qty since last signal
                    _filled = data['cumulative-filled'] - order_exec
                elif data.get('filled') is not None and data['filled'] > 0:
                    # relative data field
                    _filled = data['filled']
                else:
                    _filled = 0

                if data.get('avg-price') is not None and data['avg-price'] > 0:
                    # recompute profit-loss
                    # self.pl = self.dir * (data['avg-price'] - self.aep) / self.aep

                    # in that case we have avg-price already computed but not sufficient in case of
                    # multiple orders for exit
                    # self.axp = data['avg-price']
                    self.axp = instrument.adjust_price(((self.axp * self.x) + (data['avg-price'] * _filled)) / (
                            self.x + _filled))

                elif data.get('exec-price') is not None and data['exec-price'] > 0:
                    # increase/decrease profit/loss (over entry executed quantity)
                    # self.pl += self.dir * ((data['exec-price'] * _filled) - (self.aep * _filled)) / (
                    #     self.aep * self.e)

                    # compute the average exit price
                    self.axp = instrument.adjust_price(((self.axp * self.x) + (data['exec-price'] * _filled)) / (
                            self.x + _filled))

                if _filled > 0:
                    # update realized exit qty
                    self.x = instrument.adjust_quantity(self.x + _filled)

                    # and realized PNL
                    if self.aep > 0.0 and self.e > 0.0:
                        self.pl = self.dir * ((self.axp * self.x) - (self.aep * self.x)) / (self.aep * self.e)

                return _filled

            def update_exit_state():
                """
                Inner function to update the exit state for limit and stop order traded signals.
                """
                if self._entry_state == StrategyTrade.STATE_FILLED:
                    if self.x >= self.e or data.get('fully-filled', False):
                        # entry fully-filled : exit fully-filled or exit quantity reach entry quantity
                        self._exit_state = StrategyTrade.STATE_FILLED
                    else:
                        # entry fully-filled : exit quantity not reached entry quantity
                        self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED
                else:
                    if self.create_oid and self.e < self.oq:
                        # entry order still exists and entry quantity not reached order entry quantity
                        self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED
                    else:
                        # or there is no longer entry order then we have fully filled the exit
                        self._exit_state = StrategyTrade.STATE_FILLED

            def update_exit_stats():
                """
                Inner function to retain the trade timestamp.
                """
                if not self._stats['first-realized-exit-timestamp']:
                    self._stats['first-realized-exit-timestamp'] = data.get('timestamp', 0.0)

                self._stats['last-realized-exit-timestamp'] = data.get('timestamp', 0.0)

            def update_exit_fees_and_qty(order_cum_fees: float,
                                         order_exec: float,
                                         prev_order_exec: float,
                                         order_type: int):
                """
                Inner function to update cumulated exit fees and adjust exited quantity if necessary.
                """
                # filled fees/commissions
                _filled_commission = 0

                if data.get('cumulative-commission-amount') is None and data.get('commission-amount') is None:
                    # no value but have an order execution then compute locally
                    if order_exec > prev_order_exec:
                        # compute from instrument details
                        _maker = data.get('maker', None)

                        if _maker is None:
                            if order_type == Order.ORDER_LIMIT:
                                # @todo only if execution price is equal or better than order price
                                #  (depends on direction) or if post-only is defined
                                _maker = True  # assume maker
                            else:
                                _maker = False  # assume taker

                        # proportionate to filled qty (self._stats['notional-value'] is proportionate to self.e)
                        _filled_qty_rate = (order_exec - prev_order_exec) / self.e if self.e > 0 else 0

                        _filled_commission = (_filled_qty_rate * self._stats['notional-value']) * (
                                self.axp/self.aep) * (instrument.maker_fee if _maker else instrument.taker_fee)

                        # _filled_commission = instrument.effective_cost(order_exec - prev_order_exec, self.axp) * (
                        #     self.axp/self.aep) * (instrument.maker_fee if maker else instrument.taker_fee) * instrument.contract_size

                        if prev_order_exec == 0:
                            # for initial fill add the commission fee
                            _filled_commission += instrument.maker_commission if _maker else instrument.taker_commission

                elif data.get('cumulative-commission-amount') is not None and \
                        data['cumulative-commission-amount'] != 0 and \
                        data['cumulative-commission-amount'] != order_cum_fees:
                    # compute filled commission amount since last signal
                    _filled_commission = data['cumulative-commission-amount'] - order_cum_fees

                elif data.get('commission-amount') is not None and data['commission-amount'] != 0:
                    # relative data field
                    _filled_commission = data['commission-amount']

                # realized fees : in cumulated amount or computed from filled quantity and trade execution
                if _filled_commission != 0:
                    self._stats['exit-fees'] += _filled_commission

                return _filled_commission

            #
            # Entry
            #

            if (self.create_oid and data['id'] == self.create_oid) or (
                    ref_order_id and ref_order_id == self.create_ref_oid):

                # in case of direct traded signal without open (could occur on bitmex market order)
                if not self.eot:
                    self.eot = data['timestamp']

                # in case it occurs after position open signal and/or direct traded signal without open
                if self.e == 0:
                    self._entry_state = StrategyTrade.STATE_OPENED

                #
                # qty
                #

                prev_e = self.e

                # a single order for the entry, then it is OK and preferred to use cumulative-filled and avg-price
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
                    # compute the average entry price
                    self.aep = instrument.adjust_price(((self.aep * self.e) + (
                            data['exec-price'] * filled)) / (self.e + filled))
                else:
                    self.aep = self.op

                # cumulative filled entry qty
                if data.get('cumulative-filled') is not None and data['cumulative-filled'] > 0:
                    self.e = data.get('cumulative-filled')
                elif filled > 0:
                    self.e = instrument.adjust_quantity(self.e + filled)

                if filled > 0:
                    # probably need to update exit orders
                    self._dirty = True

                    # update notional value of the position
                    self._stats['notional-value'] = instrument.effective_cost(self.e, self.aep)

                #
                # fees/commissions
                #

                # realized fees : in cumulated or compute from filled quantity and trade execution
                if data.get('cumulative-commission-amount') is not None and \
                        data['cumulative-commission-amount'] != 0 and \
                        data['cumulative-commission-amount'] != self._stats['entry-fees']:

                    self._stats['entry-fees'] = data['cumulative-commission-amount']

                elif data.get('commission-amount') is not None and data['commission-amount'] != 0:
                    self._stats['entry-fees'] += data['commission-amount']

                elif filled > 0:
                    maker = data.get('maker', None)

                    if maker is None:
                        # no information, try to detect it
                        if self._stats.get('entry-order-type', Order.ORDER_MARKET) == Order.ORDER_LIMIT:
                            # @todo only if execution price is equal or better, then order price (depends on direction)
                            #   or if post-only
                            maker = True
                        else:
                            maker = False

                    # recompute entry-fees proportionate to notional-value
                    self._stats['entry-fees'] = self._stats['notional-value'] * (
                        instrument.maker_fee if maker else instrument.taker_fee)
                    # self._stats['entry-fees'] = self._stats['notional-value'] * (
                    #     instrument.maker_fee if maker else instrument.taker_fee) * instrument.contract_size

                    # plus the initial commission fee
                    self._stats['entry-fees'] += instrument.maker_commission if maker else instrument.taker_commission

                #
                # state
                #

                if self.e >= self.oq or data.get('fully-filled', False):
                    self._entry_state = StrategyTrade.STATE_FILLED

                    # bitmex does not send ORDER_DELETED signal, cleanup here
                    self.__reset_create()
                else:
                    self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED

                #
                # stats
                #

                # retains the trade timestamp
                if not self._stats['first-realized-entry-timestamp']:
                    self._stats['first-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                self._stats['last-realized-entry-timestamp'] = data.get('timestamp', 0.0)

            #
            # Exit Limit
            #

            elif (self.limit_oid and data['id'] == self.limit_oid) or (
                    ref_order_id and ref_order_id == self.limit_ref_oid):

                # qty
                prev_limit_order_exec = self.limit_order_exec
                filled = update_exit_qty(self.limit_order_exec)

                # cumulative filled exit qty, update trade qty and order related qty
                if filled > 0:
                    self.limit_order_exec = instrument.adjust_quantity(self.limit_order_exec + filled)

                # fees/commissions
                filled_commission = update_exit_fees_and_qty(
                    self.limit_order_cum_fees, self.limit_order_exec, prev_limit_order_exec,
                    self._stats.get('take-profit-order-type', Order.ORDER_MARKET))

                if filled_commission != 0:
                    self.limit_order_cum_fees += filled_commission

                # state
                update_exit_state()

                # order relative executed qty reached ordered qty or fully-filled flag : reset limit order state
                if self.limit_order_exec >= self.limit_order_qty or data.get('fully-filled', False):
                    self.__reset_limit()

                # stats
                update_exit_stats()

            #
            # Exit Stop
            #

            elif (self.stop_oid and data['id'] == self.stop_oid) or (
                    ref_order_id and ref_order_id == self.stop_ref_oid):

                # qty
                prev_stop_order_exec = self.stop_order_exec
                filled = update_exit_qty(self.stop_order_exec)

                # cumulative filled exit qty, update trade qty and order related qty
                if filled > 0:
                    self.stop_order_exec = instrument.adjust_quantity(self.stop_order_exec + filled)

                # fees/commissions
                filled_commission = update_exit_fees_and_qty(
                    self.stop_order_cum_fees, self.stop_order_exec, prev_stop_order_exec,
                    self._stats.get('stop-profit-order-type', Order.ORDER_MARKET))

                if filled_commission != 0:
                    self.stop_order_cum_fees += filled_commission

                # state
                update_exit_state()

                # order relative executed qty reached ordered qty or fully-filled flag : reset stop order state
                if self.stop_order_exec >= self.stop_order_qty or data.get('fully-filled', False):
                    self.__reset_stop()

                # stats
                update_exit_stats()

    def position_signal(self, signal_type: int, data: dict, ref_order_id: str, instrument: Instrument):
        if signal_type == Signal.SIGNAL_POSITION_UPDATED:
            # profit/loss update, but it is locally performed by update_stats
            if data.get('profit-loss'):
                # trade current quantity is part or total of the indivisible position
                ratio = (self.e - self.x) / data['quantity']
                self._stats['unrealized-profit-loss'] = data['profit-loss'] * ratio

            if data.get('profit-currency'):
                self._stats['profit-loss-currency'] = data['profit-currency']

        elif signal_type == Signal.SIGNAL_POSITION_DELETED:

            # filter only if the signal timestamp occurs after the creation of this trade
            if data.get('timestamp') > self.eot and self.e > 0.0:
                # no longer related position, have to clean up any related trades in case of manual close, liquidation
                self.position_id = None

                # when position closed from outside or on liquidation but this could create side effect
                # during a reversal the new trade can receive the deleted position signal and forced to be closed,
                # but it might not. maybe the timestamp could help to filter
                if self.x < self.e:
                    # @todo need to fix exit qty, exit price and exit fees as in traded signal and finally update rpnl

                    # # mean fill the rest (because qty can concerns many trades...)
                    # filled = instrument.adjust_quantity(self.e - self.x)

                    # if data.get('exec-price') is not None and data['exec-price'] > 0:
                    #     # increase/decrease profit/loss rate (over entry executed quantity)
                    #     if self.dir > 0:
                    #         self.pl += ((data['exec-price'] * filled) - (self.aep * filled)) / (self.aep * self.e)
                    #     elif self.dir < 0:
                    #         self.pl += ((self.aep * filled) - (data['exec-price'] * filled)) / (self.aep * self.e)

                    # update average exit price
                    # @todo

                    # update realized exit qty
                    self.x = self.e

                    # and realized PNL
                    if self.aep > 0.0 and self.e > 0.0:
                        self.pl = self.dir * ((self.axp * self.x) - (self.aep * self.x)) / (self.aep * self.e)

                if self._exit_state != StrategyTrade.STATE_FILLED:
                    # that will cause to remove the trade and then related orders
                    self._exit_state = StrategyTrade.STATE_FILLED

                    # for stats
                    self._stats['last-realized-exit-timestamp'] = data.get('timestamp', 0.0)

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

        data['stop-order-exec'] = self.stop_order_exec
        data['limit-order-exec'] = self.limit_order_exec

        data['stop-order-cum-fees'] = self.stop_order_cum_fees
        data['limit-order-cum-fees'] = self.limit_order_cum_fees

        return data

    def loads(self, data: dict, strategy_trader: StrategyTraderBase) -> bool:
        if not super().loads(data, strategy_trader):
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

        self.stop_order_exec = data.get('stop-order-exec', 0.0)
        self.limit_order_exec = data.get('limit-order-exec', 0.0)

        self.stop_order_cum_fees = data.get('stop-order-cum-fees', 0.0)
        self.limit_order_cum_fees = data.get('limit-order-cum-fees', 0.0)

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
                    self.__reset_create()
                else:
                    self.fix_by_order(data, instrument, self.e)

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
                    self.__reset_stop()
                else:
                    self.fix_by_order(data, instrument, self.stop_order_exec)

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

                    # no longer limit order
                    self.__reset_limit()
                else:
                    self.fix_by_order(data, instrument, self.limit_order_exec)

        return result

    def fix_by_order(self, order_data: dict, instrument: Instrument, quantity: float) -> bool:
        """
        Mostly an internal method used to fix a missed and closed order, fixing the realized quantity.

        @param order_data:
        @param instrument:
        @param quantity:
        @return:
        """
        if not order_data or not instrument:
            return False

        if 'cumulative-filled' not in order_data or 'fully-filled' not in order_data:
            return False

        if 'ref-id' not in order_data:
            return False

        if order_data['cumulative-filled'] > quantity or order_data['fully-filled']:
            self.order_signal(Signal.SIGNAL_ORDER_TRADED, order_data, order_data['ref-id'], instrument)

        if 'status' not in order_data:
            return False

        if order_data['status'] in ('closed', 'deleted'):
            self.order_signal(Signal.SIGNAL_ORDER_DELETED, order_data['id'], order_data['ref-id'], instrument)

        elif order_data['status'] in ('expired', 'canceled'):
            self.order_signal(Signal.SIGNAL_ORDER_CANCELED, order_data['id'], order_data['ref-id'], instrument)

    def repair(self, trader: Trader, instrument: Instrument) -> bool:
        # @todo fix the trade

        return False

    #
    # stats
    #

    def update_stats(self, instrument: Instrument, timestamp: float):
        super().update_stats(instrument, timestamp)

        if self.is_active():
            last_price = instrument.close_exec_price(self.direction)
            if last_price <= 0:
                return

            # non realized quantity
            nrq = self.e - self.x

            u_pnl = instrument.compute_pnl(nrq, self.dir, self.aep, last_price)
            r_pnl = instrument.compute_pnl(self.x, self.dir, self.aep, self.axp)

            # including fees and realized profit and loss
            self._stats['unrealized-profit-loss'] = instrument.adjust_settlement(
                u_pnl + r_pnl - self._stats['entry-fees'] - self._stats['exit-fees'] - self._stats['margin-fees'])

    def info_report(self, strategy_trader: StrategyTraderBase) -> Tuple[str]:
        data = list(super().info_report(strategy_trader))

        entry_fees = "%g" % self._stats['entry-fees']

        if self.create_oid or self.create_ref_oid:
            data.append("Entry order id / ref : %s / %s" % (self.create_oid, self.create_ref_oid))
            data.append("- Qty %s / Exec %s / Fees %s" % (strategy_trader.instrument.format_quantity(self.oq),
                                                          strategy_trader.instrument.format_quantity(self.e),
                                                          entry_fees))

        if self.stop_oid or self.stop_ref_oid:
            stop_order_fees = "%g" % self.stop_order_cum_fees

            data.append("Stop order id / ref : %s / %s" % (self.stop_oid, self.stop_ref_oid))
            data.append("- Qty %s / Exec %s / Fees %s" % (
                strategy_trader.instrument.format_quantity(self.stop_order_qty),
                strategy_trader.instrument.format_quantity(self.stop_order_exec),
                stop_order_fees))

        if self.limit_oid or self.limit_ref_oid:
            limit_order_fees = "%g" % self.limit_order_cum_fees

            data.append("Limit order id / ref : %s / %s" % (self.limit_oid, self.limit_ref_oid))
            data.append("- Qty %s / Exec %s / Fees %s" % (
                strategy_trader.instrument.format_quantity(self.limit_order_qty),
                strategy_trader.instrument.format_quantity(self.limit_order_exec),
                limit_order_fees))

        if self.position_id:
            data.append("Position id : %s" % (self.position_id,))

        exit_fees = "%g" % self._stats['exit-fees']
        margin_fees = "%g" % self._stats['margin-fees']
        total_fees = "%g" % (self._stats['entry-fees'] + self._stats['exit-fees'] + self._stats['margin-fees'])

        data.append("Cumulated fees : Entry %s / Exit %s / Margin %s / Total %s" % (
            entry_fees, exit_fees, margin_fees, total_fees))

        return tuple(data)

    #
    # private
    #

    def __reset_create(self):
        # reset for remove
        self.create_ref_oid = None
        self.create_oid = None

    def __reset_stop(self):
        # reset for new order
        self.stop_oid = None
        self.stop_ref_oid = None
        self.stop_order_qty = 0.0
        self.stop_order_exec = 0.0
        self.stop_order_cum_fees = 0.0

    def __reset_limit(self):
        # reset for new order
        self.limit_oid = None
        self.limit_ref_oid = None
        self.limit_order_qty = 0.0
        self.limit_order_exec = 0.0
        self.limit_order_cum_fees = 0.0

    def __check_and_reset_create(self, trader: Trader, instrument: Instrument):
        if self.create_oid:
            # check create_oid closed order state qty : must be still unchanged or fix it
            order_data = trader.order_info(self.create_oid, instrument)

            if order_data and order_data['id']:
                # realized qty changed between
                if order_data['cumulative-filled'] > self.e:
                    self.order_signal(Signal.SIGNAL_ORDER_TRADED, order_data, order_data['ref-id'], instrument)

        self.__reset_create()

    def __check_and_reset_stop(self, trader: Trader, instrument: Instrument):
        if self.stop_oid:
            order_data = trader.order_info(self.stop_oid, instrument)

            if order_data and order_data['id']:
                # realized qty changed between
                if order_data['cumulative-filled'] > self.stop_order_exec:
                    self.order_signal(Signal.SIGNAL_ORDER_TRADED, order_data, order_data['ref-id'], instrument)

        self.__reset_stop()

    def __check_and_reset_limit(self, trader: Trader, instrument: Instrument):
        if self.limit_oid:
            order_data = trader.order_info(self.limit_oid, instrument)

            if order_data and order_data['id']:
                # realized qty changed between
                if order_data['cumulative-filled'] > self.limit_order_exec:
                    self.order_signal(Signal.SIGNAL_ORDER_TRADED, order_data, order_data['ref-id'], instrument)

        self.__reset_limit()
