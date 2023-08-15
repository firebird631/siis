# @date 2018-12-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade for asset.

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from trader.trader import Trader
    from instrument.instrument import Instrument
    from strategy.strategytrader import StrategyTrader

from common.signal import Signal
from trader.order import Order

from .strategytrade import StrategyTrade

import logging
logger = logging.getLogger('siis.strategy.assettrade')
error_logger = logging.getLogger('siis.error.strategy.assettrade')


class StrategyAssetTrade(StrategyTrade):
    """
    Specialization for asset trading : first buy (entry) then sell (exit).
    Only a single initial buy order, and a single exit order (either stop or limit order).

    @todo support of OCO order (close, remove, modify, cancel) if available from market or a specialized model

    @todo improve trade management in case of fees are in base asset :
        to know if an exit order is complete it could compare limit/stop_order_qty and limit/stop_exec_qty even
        in the case where fees are taken on base asset because if we deduce this amount from
        limit/stop_order_qty and limit/stop_exec_qty comparison will be ok

    @todo before close or modifying or canceling stop or limit it is important to compute the notional size
        and to compare with the instrument min-notional size, because else it will be impossible to recreate
        a sell order with the remaining quantity.
    """

    __slots__ = 'entry_ref_oid', 'stop_ref_oid', 'limit_ref_oid', 'oco_ref_oid', \
                'entry_oid', 'stop_oid', 'limit_oid', 'oco_oid', '_use_oco', \
                'stop_order_qty', 'limit_order_qty', \
                'stop_order_exec', 'limit_order_exec', \
                'stop_order_cum_fees', 'limit_order_cum_fees'

    def __init__(self, timeframe: float):
        super().__init__(StrategyTrade.TRADE_BUY_SELL, timeframe)

        self.entry_ref_oid = None
        self.stop_ref_oid = None
        self.limit_ref_oid = None
        self.oco_ref_oid = None

        self.entry_oid = None       # entry buy order id
        self.stop_oid = None        # exit sell stop order id
        self.limit_oid = None       # exit sell limit order id
        self.oco_oid = None         # exit sell OCO order id

        self._use_oco = False   # True if OCO order is used

        self.stop_order_qty = 0.0         # ordered quantity of the current stop order
        self.limit_order_qty = 0.0        # ordered quantity of the current limit order

        self.stop_order_exec = 0.0        # executed quantity of the current stop order
        self.limit_order_exec = 0.0       # executed quantity of the current limit order

        self.stop_order_cum_fees = 0.0    # cumulative fees quantity of the current stop order
        self.limit_order_cum_fees = 0.0   # cumulative fees quantity of the current limit order

    def open(self, trader: Trader, instrument: Instrument, direction: int, order_type: int,
             order_price: float, quantity: float, take_profit: float, stop_loss: float,
             leverage: float = 1.0, hedging: Optional[bool] = None, use_oco: Optional[bool] = None) -> bool:
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
        self._stats['profit-loss-currency'] = instrument.quote

        if trader.create_order(order, instrument) > 0:
            self.entry_oid = order.order_id

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

        # generated a reference order id
        trader.set_ref_order_id(order)
        self.entry_ref_oid = order.ref_order_id

        self.oq = order.quantity  # ordered quantity

        if trader.create_order(order, instrument) > 0:
            self.entry_oid = order.order_id

            if not self.eot and order.created_time:
                # only at the first open
                self.eot = order.created_time

            return True
        else:
            self._entry_state = StrategyTrade.STATE_REJECTED
            return False

    def remove(self, trader: Trader, instrument: Instrument) -> int:
        error = False

        if self.entry_oid:
            # cancel the remaining buy order
            if trader.cancel_order(self.entry_oid, instrument) > 0:
                # check entry_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_entry(trader, instrument)

                if self.e <= 0:
                    # no entry qty processed, entry canceled
                    self._entry_state = StrategyTrade.STATE_CANCELED
                else:
                    # cancel a partially filled trade means it is then fully filled
                    self._entry_state = StrategyTrade.STATE_FILLED
            else:
                data = trader.order_info(self.entry_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    error = True

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no entry order, nothing to do
                    self.entry_ref_oid = None
                    self.entry_oid = None

                    self._entry_state = StrategyTrade.STATE_CANCELED
                else:
                    # exists, do nothing need to retry
                    error = True

        if self.oco_oid:
            # cancel the oco sell order
            if trader.cancel_order(self.oco_oid, instrument) > 0:
                # @todo must check stop and limit order state and fix it if necessary

                self.oco_ref_oid = None
                self.oco_oid = None

                self.__reset_stop()
                self.__reset_limit()

                if self.e <= 0 and self.x <= 0:
                    # no exit qty
                    self._exit_state = StrategyTrade.STATE_CANCELED
                elif self.x >= self.e:
                    self._exit_state = StrategyTrade.STATE_FILLED
                else:
                    self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED
            else:
                data = trader.order_info(self.oco_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    error = True

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no entry order, nothing to do
                    self.oco_ref_oid = None
                    self.oco_oid = None
                else:
                    # exists, do nothing need to retry
                    error = True
        else:
            if self.stop_oid:
                # cancel the stop sell order
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
                    data = trader.order_info(self.stop_oid, instrument)

                    if data is None:
                        # API error, do nothing need retry
                        error = True

                    elif data['id'] is None:
                        # cannot retrieve the order, wrong id, no stop order
                        self.__reset_stop()
                    else:
                        error = True

            if self.limit_oid:
                # cancel the sell limit order
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
                    data = trader.order_info(self.limit_oid, instrument)

                    if data is None:
                        # API error, do nothing need retry
                        error = True

                    elif data['id'] is None:
                        # cannot retrieve the order, wrong id, no stop order
                        self.__reset_limit()
                    else:
                        error = True

        return not error

    def cancel_open(self, trader: Trader, instrument: Instrument) -> int:
        """
        @todo Before cancel, if the realized quantity is lesser than the min-notional it
        will be impossible to create an exit order.
        """
        if self.entry_oid:
            # cancel the buy order
            if trader.cancel_order(self.entry_oid, instrument) > 0:
                # check entry_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_entry(trader, instrument)

                if self.e <= 0:
                    # cancel a just opened trade means it is canceled
                    self._entry_state = StrategyTrade.STATE_CANCELED
                else:
                    # cancel a partially filled trade means it is then fully filled
                    self._entry_state = StrategyTrade.STATE_FILLED

                return self.ACCEPTED
            else:
                data = trader.order_info(self.entry_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no entry order, nothing to do
                    self.entry_ref_oid = None
                    self.entry_oid = None

                    self._entry_state = StrategyTrade.STATE_CANCELED
                else:
                    # exists, do nothing need to retry
                    return self.ERROR

        return self.NOTHING_TO_DO

    def cancel_close(self, trader: Trader, instrument: Instrument) -> int:
        """
        @todo for OCO
        """
        if self.oco_oid:
            pass

        elif self.limit_oid:
            # cancel the sell order
            if trader.cancel_order(self.limit_oid, instrument) > 0:
                # check limit_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_limit(trader, instrument)

                if self.x <= 0:
                    self._exit_state = StrategyTrade.STATE_CANCELED

                return self.ACCEPTED
            else:
                data = trader.order_info(self.entry_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no entry order, nothing to do
                    self.__reset_limit()

                    self._exit_state = StrategyTrade.STATE_CANCELED
                else:
                    # exists, do nothing need to retry
                    return self.ERROR

        elif self.stop_oid:
            # cancel the sell order
            if trader.cancel_order(self.stop_oid, instrument) > 0:
                # check stop_oid closed order state qty : must be still unchanged or fix it
                self.__check_and_reset_stop(trader, instrument)

                if self.x <= 0:
                    self._exit_state = StrategyTrade.STATE_CANCELED

                return self.ACCEPTED
            else:
                data = trader.order_info(self.entry_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    return self.ERROR

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no entry order, nothing to do
                    self.__reset_stop()

                    self._exit_state = StrategyTrade.STATE_CANCELED
                else:
                    # exists, do nothing need to retry
                    return self.ERROR

        return self.NOTHING_TO_DO

    def modify_take_profit(self, trader: Trader, instrument: Instrument, limit_price: float, hard: bool = True) -> int:
        """
        @todo Before cancel, if the remaining quantity is lesser than the min-notional it will be impossible
        to create a new order.

        @note If hard is True and an hard stop order exists it will be removed.
        """
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

            if self.stop_oid and hard:
                # cancel the sell stop order (only one or the other)
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
                # all entry qty is filled
                return self.NOTHING_TO_DO

            if limit_price and hard:
                order = Order(trader, instrument.market_id)
                order.direction = -self.dir  # neg dir
                order.order_type = Order.ORDER_LIMIT
                order.price = limit_price
                order.quantity = self.e - self.x  # remaining

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
                    # REST sync
                    self.limit_oid = order.order_id

                    self.last_tp_ot[0] = order.created_time
                    self.last_tp_ot[1] += 1

                    self.tp = limit_price

                    return self.ACCEPTED
                elif create_order_result == Order.REASON_INSUFFICIENT_FUNDS:
                    # rejected because not enough margin, must stop to retry
                    self.__reset_limit()
                    self._exit_state = self.STATE_ERROR

                    return self.INSUFFICIENT_FUNDS
                else:
                    # rejected
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
        """
        @todo Before cancel, if the remaining quantity is lesser than the min-notional it will be impossible
        to create a new order.

        @note If hard is True and an hard limit order exists it will be removed.
        """
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

            if self.limit_oid and hard:
                # cancel the sell limit order (only one or the other)
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
                # all entry qty is filled
                return self.NOTHING_TO_DO

            if stop_price and hard:
                order = Order(trader, instrument.market_id)
                order.direction = -self.dir  # neg dir
                order.order_type = Order.ORDER_STOP
                order.stop_price = stop_price
                order.quantity = self.e - self.x  # remaining

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
                    # REST sync
                    self.stop_oid = order.order_id

                    self.last_stop_ot[0] = order.created_time
                    self.last_stop_ot[1] += 1

                    self.sl = stop_price

                    return self.ACCEPTED
                elif create_order_result == Order.REASON_INSUFFICIENT_FUNDS:
                    # rejected because not enough margin, must stop to retry
                    self.__reset_stop()
                    self._exit_state = self.STATE_ERROR

                    return self.INSUFFICIENT_FUNDS
                else:
                    # rejected
                    self.__reset_stop()
                    return self.REJECTED
            elif stop_price:
                # soft stop-loss
                self.sl = stop_price
            else:
                # remove stop-loss
                self.sl = 0.0

            return self.NOTHING_TO_DO

    def modify_oco(self, trader: Trader, instrument: Instrument, limit_price: float, stop_price: float,
                   hard: bool = True) -> int:
        # @todo

        return self.REJECTED

    def close(self, trader: Trader, instrument: Instrument) -> int:
        """
        @todo Before cancel, if the remaining quantity is lesser than the min-notional it will be impossible
        to create a new order.
        """
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
                if trader.cancel_order(self.entry_oid, instrument) > 0:
                    # check entry_oid closed order state qty : must be still unchanged or fix it
                    self.__check_and_reset_entry(trader, instrument)
                else:
                    data = trader.order_info(self.entry_oid, instrument)

                    if data is None:
                        # API error, do nothing need retry
                        return self.ERROR

                    elif data['id'] is None:
                        # cannot retrieve the order, wrong id, no entry order
                        self.entry_ref_oid = None
                        self.entry_oid = None
                    else:
                        return self.ERROR

            if self.limit_oid:
                # cancel the sell limit order
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

            if self.stop_oid:
                # cancel the sell stop order and create a new one
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
                # all qty is filled
                return self.NOTHING_TO_DO

            order = Order(trader, instrument.market_id)
            order.direction = -self.dir  # neg dir
            order.order_type = Order.ORDER_MARKET
            order.quantity = self.e - self.x  # remaining qty

            self._stats['stop-order-type'] = order.order_type

            # generated a reference order id and keep it before ordering to retrieve its signals
            trader.set_ref_order_id(order)

            # set before in case of async signal comes before
            self.stop_ref_oid = order.ref_order_id
            self.stop_order_qty = order.quantity
            self.stop_order_exec = 0.0
            self.stop_order_cum_fees = 0.0

            create_order_result = trader.create_order(order, instrument)
            if create_order_result > 0:
                # REST sync
                self.stop_oid = order.order_id

                # closing order defined
                self._closing = True

                return self.ACCEPTED
            elif create_order_result == Order.REASON_INSUFFICIENT_FUNDS:
                # rejected because not enough margin, must stop to retry
                self.__reset_stop()
                self._exit_state = self.STATE_ERROR

                return self.INSUFFICIENT_FUNDS
            else:
                # rejected
                self.__reset_stop()
                return self.REJECTED

    def has_stop_order(self) -> bool:
        return self.stop_oid is not None and self.stop_oid != ""

    def has_limit_order(self) -> bool:
        return self.limit_oid is not None and self.limit_oid != ""

    def has_oco_order(self) -> bool:
        return self.oco_oid is not None and self.oco_oid != ""

    def support_both_order(self) -> bool:
        if self.has_oco_order():
            # only if an OCO order is defined
            return True
        else:
            return False

    @classmethod
    def is_margin(cls) -> bool:
        return False

    @classmethod
    def is_spot(cls) -> bool:
        return True

    #
    # signals
    #

    def update_dirty(self, trader: Trader, instrument: Instrument):
        # result invalid done only on error, but previously it was also invalided by a nothing to do.
        if self._dirty:
            done = True

            if self.has_oco_order():
                # @todo done = False
                pass
            else:
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

    def is_target_order(self, order_id: str, ref_order_id: str) -> bool:
        if order_id and (order_id == self.entry_oid or order_id == self.stop_oid or
                         order_id == self.limit_oid or order_id == self.oco_oid):
            return True

        if ref_order_id and (ref_order_id == self.entry_ref_oid or ref_order_id == self.stop_ref_oid or
                             ref_order_id == self.limit_ref_oid or ref_order_id == self.oco_ref_oid):
            return True

        return False

    def order_signal(self, signal_type: int, data: dict, ref_order_id: str, instrument: Instrument):
        if signal_type == Signal.SIGNAL_ORDER_OPENED:
            # already get at the return of create_order
            if ref_order_id and ref_order_id == self.entry_ref_oid:
                self.entry_oid = data['id']

                # init created timestamp at the create order open
                if not self.eot:
                    self.eot = data['timestamp']

                if data.get('stop-loss'):
                    self.sl = data['stop-loss']

                if data.get('take-profit'):
                    self.tp = data['take-profit']

                self._entry_state = StrategyTrade.STATE_OPENED

            elif ref_order_id and ref_order_id == self.stop_ref_oid:
                self.stop_oid = data['id']

                if not self.xot:
                    self.xot = data['timestamp']

                self._exit_state = StrategyTrade.STATE_OPENED

            elif ref_order_id and ref_order_id == self.limit_ref_oid:
                self.limit_oid = data['id']

                if not self.xot:
                    self.xot = data['timestamp']

                self._exit_state = StrategyTrade.STATE_OPENED

        elif signal_type == Signal.SIGNAL_ORDER_TRADED:
            # update the trade quantity
            if 'filled' not in data and 'cumulative-filled' not in data:
                return

            def update_exit_qty(order_exec):
                """
                Inner function to update the exit qty.
                """
                if data.get('cumulative-filled') is not None and data['cumulative-filled'] > order_exec:
                    # compute filled qty since last signal
                    _filled = data['cumulative-filled'] - order_exec
                elif data.get('filled') is not None and data['filled'] > 0:
                    # relative data field
                    _filled = data['filled']
                else:
                    _filled = 0

                if data.get('exec-price') is not None and data['exec-price'] > 0 and _filled > 0:
                    # profit/loss when reducing the trade (over executed entry qty)
                    self.pl += ((data['exec-price'] * _filled) - (self.aep * _filled)) / (self.aep * self.e)

                    # average exit price
                    self.axp = instrument.adjust_price(((self.axp * self.x) + (
                            data['exec-price'] * _filled)) / (self.x + _filled))

                # elif data.get('avg-price') is not None and data['avg-price'] > 0:
                #     # average price is directly given
                #     self.pl = ((data['avg-price'] * (self.x + filled)) - (self.aep * filled)) / (self.aep * self.e)

                #     # average exit price
                #     self.axp = data['avg-price']

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
                    if self.entry_oid and self.e < self.oq:
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
                        # @todo compute on quote or on base or let zero
                        pass
                        # _filled_commission = (order_exec - prev_order_exec) * (
                        #     instrument.maker_fee if data.get('maker', False) else instrument.taker_fee)

                elif data.get('cumulative-commission-amount') is not None and \
                        data['cumulative-commission-amount'] > order_cum_fees:
                    # compute filled commission amount since last signal
                    _filled_commission = data['cumulative-commission-amount'] - order_cum_fees

                elif data.get('commission-amount') is not None and data['commission-amount'] > 0:
                    # relative data field
                    _filled_commission = data['commission-amount']

                # realized fees : in cumulated quote or computed from filled quantity and trade execution
                if _filled_commission > 0:
                    # commission asset is asset, have to reduce it from filled exit qty
                    if data.get('commission-asset', "") == instrument.base:
                        self.x = instrument.adjust_quantity(self.x - _filled_commission)

                    self._stats['exit-fees'] += _filled_commission

                return _filled_commission

            #
            # Entry
            #

            if ((self.entry_oid and data['id'] == self.entry_oid) or (
                    ref_order_id and ref_order_id == self.entry_ref_oid)):

                # it is preferred to use cumulative-filled and avg-price because precision comes from the broker
                if data.get('cumulative-filled') is not None and data['cumulative-filled'] > 0:
                    # compute filled qty since last signal
                    filled = data['cumulative-filled'] - self.e  # compute filled qty
                elif data.get('filled') is not None and data['filled'] > 0:
                    # relative data field
                    filled = data['filled']
                else:
                    filled = 0

                if data.get('avg-price') is not None and data['avg-price'] > 0:
                    # average entry price is directly given
                    self.aep = data['avg-price']

                elif data.get('exec-price') is not None and data['exec-price'] > 0 and filled > 0:
                    # compute the average entry price whe increasing the trade
                    self.aep = instrument.adjust_price(((self.aep * self.e) + (
                            data['exec-price'] * filled)) / (self.e + filled))

                # cumulative filled entry qty
                if data.get('cumulative-filled') is not None and data['cumulative-filled'] > 0:
                    self.e = data.get('cumulative-filled')
                elif filled > 0:
                    self.e = instrument.adjust_quantity(self.e + filled)

                if filled > 0:
                    # probably need to update exit orders
                    self._dirty = True

                #
                # fees/commissions
                #

                if (data.get('commission-asset', "") == instrument.base) and (data.get('commission-amount', 0) > 0):
                    # commission asset is itself, have to reduce it from filled, done after status determination
                    # because of the qty reduced by the fee
                    self.e = instrument.adjust_quantity(self.e - data.get('commission-amount', 0.0))

                # realized fees : in cumulated quote or compute from filled quantity and trade execution
                if 'cumulative-commission-amount' in data:
                    self._stats['entry-fees'] = data['cumulative-commission-amount']
                elif 'commission-amount' in data:
                    self._stats['entry-fees'] += data['commission-amount']
                # else:
                #     self._stats['entry-fees'] += filled * (instrument.maker_fee if data.get(
                #         'maker', False) else instrument.taker_fee)

                #
                # state
                #

                if self.e >= self.oq or data.get('fully-filled', False):
                    self._entry_state = StrategyTrade.STATE_FILLED

                    # it means also entry order completed and then no longer exists
                    self.__reset_entry()
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
                    self.x = instrument.adjust_quantity(self.x + filled)
                    self.limit_order_exec = instrument.adjust_quantity(self.limit_order_exec + filled)

                # fees/commissions
                update_exit_fees_and_qty(self.limit_order_cum_fees, self.limit_order_exec, prev_limit_order_exec,
                                         self._stats.get('take-profit-order-type', Order.ORDER_MARKET))

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
                    self.x = instrument.adjust_quantity(self.x + filled)
                    self.stop_order_exec = instrument.adjust_quantity(self.stop_order_exec + filled)

                # fees/commissions
                update_exit_fees_and_qty(self.stop_order_cum_fees, self.stop_order_exec, prev_stop_order_exec,
                                         self._stats.get('stop-order-type', Order.ORDER_MARKET))

                # state
                update_exit_state()

                # order relative executed qty reached ordered qty or fully-filled flag : reset stop order state
                if self.stop_order_exec >= self.stop_order_qty or data.get('fully-filled', False):
                    self.__reset_stop()

                # stats
                update_exit_stats()

        elif signal_type == Signal.SIGNAL_ORDER_UPDATED:
            # order price or qty modified
            # but it is rarely possible
            pass

        elif signal_type == Signal.SIGNAL_ORDER_DELETED:
            # order is no longer active
            if not data:
                return

            if data == self.entry_oid:
                self.__reset_entry()

                if self.e > 0:
                    # entry order deleted but some qty exists means entry is fully filled
                    self._entry_state = StrategyTrade.STATE_FILLED

            elif data == self.stop_oid:
                self.__reset_stop()

            elif data == self.limit_oid:
                self.__reset_limit()

        elif signal_type == Signal.SIGNAL_ORDER_REJECTED:
            # order is rejected
            if not data:
                return

            if data == self.entry_ref_oid:
                self.__reset_entry()
                self._entry_state = StrategyTrade.STATE_REJECTED

            elif data == self.stop_ref_oid:
                self.__reset_stop()

            elif data == self.limit_ref_oid:
                self.__reset_limit()

        elif signal_type == Signal.SIGNAL_ORDER_CANCELED:
            # order is no longer active
            if not data:
                return

            if data == self.entry_oid:
                self.__reset_entry()

                if self.e > 0:
                    # entry order canceled but some qty exists means entry is fully filled
                    self._entry_state = StrategyTrade.STATE_FILLED

            elif data == self.stop_oid:
                self.__reset_stop()

            elif data == self.limit_oid:
                self.__reset_limit()

    def dumps(self) -> dict:
        data = super().dumps()

        data['entry-ref-oid'] = self.entry_ref_oid
        data['entry-oid'] = self.entry_oid

        data['stop-ref-oid'] = self.stop_ref_oid
        data['stop-oid'] = self.stop_oid

        data['limit-ref-oid'] = self.limit_ref_oid
        data['limit-oid'] = self.limit_oid

        data['oco-ref-oid'] = self.oco_ref_oid
        data['oco-oid'] = self.oco_oid

        data['stop-order-qty'] = self.stop_order_qty
        data['limit-order-qty'] = self.limit_order_qty

        data['stop-order-exec'] = self.stop_order_exec
        data['limit-order-exec'] = self.limit_order_exec

        data['stop-order-cum-fees'] = self.stop_order_cum_fees
        data['limit-order-cum-fees'] = self.limit_order_cum_fees

        return data

    def loads(self, data: dict, strategy_trader: StrategyTrader) -> bool:
        if not super().loads(data, strategy_trader):
            return False

        self.entry_ref_oid = data.get('entry-ref-oid', None)
        self.entry_oid = data.get('entry-oid', None)

        self.stop_ref_oid = data.get('stop-ref-oid', None)
        self.stop_oid = data.get('stop-oid', None)

        self.limit_ref_oid = data.get('limit-ref-oid', None)
        self.limit_oid = data.get('limit-oid', None)

        self.oco_ref_oid = data.get('oco-ref-oid', None)
        self.oco_oid = data.get('oco-oid', None)

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

        if self.entry_oid:
            data = trader.order_info(self.entry_oid, instrument)

            if data is None:
                # API error, do nothing need retry
                result = -1
            else:
                if data['id'] is None:
                    # cannot retrieve the order, wrong id
                    result = 0

                    # no longer entry order
                    self.__reset_entry()
                else:
                    self.fix_by_order(data, instrument, self.e)

        #
        # exit
        #

        if self.oco_oid:
            # have an OCO order
            data = trader.order_info(self.oco_oid, instrument)

            if data is None:
                # API error, do nothing need retry
                result = -1
            else:
                if data['id'] is None:
                    # cannot retrieve the order, wrong id
                    result = 0

                    # no longer OCO order
                    self.oco_oid = None
                    self.oco_ref_oid = None
                else:
                    pass
        else:
            if self.stop_oid:
                data = trader.order_info(self.stop_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    result = -1
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
            # change in executed qty
            self.order_signal(Signal.SIGNAL_ORDER_TRADED, order_data, order_data['ref-id'], instrument)

        if 'status' not in order_data:
            return False

        if order_data['status'] in ('closed', 'deleted'):
            self.order_signal(Signal.SIGNAL_ORDER_DELETED, order_data['id'], order_data['ref-id'], instrument)

        elif order_data['status'] in ('expired', 'canceled'):
            self.order_signal(Signal.SIGNAL_ORDER_CANCELED, order_data['id'], order_data['ref-id'], instrument)

    def repair(self, trader: Trader, instrument: Instrument) -> bool:
        # @todo fix the trade
        # is entry or exit in error
        # if entry is partially filled or none
        # - if none state canceled entry, none exit
        # - if qty check free size and create an exit order if min notional...
        # if exit in error
        # - if entry qty > 0 recreate exit order if min notional...
        # if no min notional, free qty... let the error status

        return False

    #
    # stats
    #

    def update_stats(self, instrument: Instrument, timestamp: float):
        super().update_stats(instrument, timestamp)

        if self.is_active():
            last_price = instrument.close_exec_price(self.direction)

            if last_price > 0.0:
                upnl = 0.0  # unrealized PNL
                rpnl = 0.0  # realized PNL

                # non realized quantity
                nrq = self.e - self.x

                if self.dir > 0:
                    upnl = last_price * nrq - self.aep * nrq
                    rpnl = self.axp * self.x - self.aep * self.x
                elif self.dir < 0:
                    upnl = self.aep * nrq - last_price * nrq
                    rpnl = self.aep * self.x - self.axp * self.x

                # including fees and realized profit and loss
                self._stats['unrealized-profit-loss'] = instrument.adjust_quote(
                    upnl + rpnl - self._stats['entry-fees'] - self._stats['exit-fees'])

    def info_report(self, strategy_trader: StrategyTrader) -> Tuple[str]:
        data = list(super().info_report(strategy_trader))

        if self.entry_oid or self.entry_ref_oid:
            data.append("Entry order id / ref : %s / %s" % (self.entry_oid, self.entry_ref_oid))
            data.append("- Qty %g / Exec %g / Fees %g" % (self.oq, self.e, self._stats['entry-fees']))

        if self.stop_oid or self.stop_ref_oid:
            data.append("Stop order id / ref : %s / %s" % (self.stop_oid, self.stop_ref_oid))
            data.append("- Qty %g / Exec %g / Fees %g" % (
                self.stop_order_qty, self.stop_order_exec, self.stop_order_cum_fees))

        if self.limit_oid or self.limit_ref_oid:
            data.append("Limit order id / ref : %s / %s" % (self.limit_oid, self.limit_ref_oid))
            data.append("- Qty %g / Exec %g / Fees %g" % (
                self.limit_order_qty, self.limit_order_exec, self.limit_order_cum_fees))

        if self.oco_oid or self.oco_ref_oid:
            data.append("OCO order id / ref : %s / %s" % (self.oco_oid, self.oco_ref_oid))

        return tuple(data)

    #
    # private
    #

    def __reset_entry(self):
        # reset for remove
        self.entry_ref_oid = None
        self.entry_oid = None

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

    def __check_and_reset_entry(self, trader: Trader, instrument: Instrument):
        if self.entry_oid:
            # check entry_oid closed order state qty : must be still unchanged or fix it
            order_data = trader.order_info(self.entry_oid, instrument)

            if order_data and order_data['id']:
                # realized qty changed between, only process traded signal
                if order_data['cumulative-filled'] > self.e:
                    self.order_signal(Signal.SIGNAL_ORDER_TRADED, order_data, order_data['ref-id'], instrument)

        self.__reset_entry()

    def __check_and_reset_stop(self, trader: Trader, instrument: Instrument):
        if self.stop_oid:
            order_data = trader.order_info(self.stop_oid, instrument)

            if order_data and order_data['id']:
                # realized qty changed between, only process traded signal
                if order_data['cumulative-filled'] > self.stop_order_exec:
                    self.order_signal(Signal.SIGNAL_ORDER_TRADED, order_data, order_data['ref-id'], instrument)

        self.__reset_stop()

    def __check_and_reset_limit(self, trader: Trader, instrument: Instrument):
        if self.limit_oid:
            order_data = trader.order_info(self.limit_oid, instrument)

            if order_data and order_data['id']:
                # realized qty changed between, only process traded signal
                if order_data['cumulative-filled'] > self.limit_order_exec:
                    self.order_signal(Signal.SIGNAL_ORDER_TRADED, order_data, order_data['ref-id'], instrument)

        self.__reset_limit()
