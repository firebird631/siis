# @date 2018-12-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade for margin individual position

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from trader.trader import Trader
    from instrument.instrument import Instrument
    from strategy.strategytrader import StrategyTrader

from common.signal import Signal
from trader.order import Order

from .strategytrade import StrategyTrade

import logging
logger = logging.getLogger('siis.strategy.positiontrade')


class StrategyPositionTrade(StrategyTrade):
    """
    Specialization for margin individual position trading. 

    This type of trade is related to margin trading market, allowing hedging.
    Works with CFD brokers (ig...).

    Hedging must be true by to manage position into the two direction at the same time.
    """

    __slots__ = 'create_ref_oid', 'create_oid', 'position_id', 'position_stop', 'position_limit', \
                'position_quantity', 'leverage', 'hedging'

    def __init__(self, timeframe):
        super().__init__(StrategyTrade.TRADE_POSITION, timeframe)

        self.create_ref_oid = None

        self.create_oid = None   # related entry order id
        self.position_id = None  # related position id

        self.position_stop = 0.0      # Non-zero mean position had a stop defined on broker side
        self.position_limit = 0.0     # Non-zero mean position had a limit defined on broker side
        self.position_quantity = 0.0  # Current position quantity

        self.leverage = 1.0
        self.hedging = False

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
        order.order_type = order_type
        order.quantity = quantity
        order.leverage = leverage
        order.margin_trade = True
        order.post_only = False

        if order_type == Order.ORDER_LIMIT:
            order.price = order_price

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
        self.hedging = hedging

        self._stats['entry-order-type'] = order.order_type

        if trader.create_order(order, instrument) > 0:
            # keep the related position identifier if available (maybe be even if pending)
            self.create_oid = order.order_id
            self.position_id = order.position_id  # mostly the same id as order-id

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
        order.order_type = self._stats['entry-order-type']
        order.quantity = quantity
        order.post_only = False
        order.margin_trade = True
        order.leverage = self.leverage

        if order.order_type == Order.ORDER_LIMIT:
            order.price = self.op

        if self.hedging:
            order.hedging = self.hedging

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
        Remove the order, but doesn't close the position.
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
                data = trader.order_info(self.create_oid, instrument)

                if data is None:
                    # API error, do nothing need retry
                    error = True

                elif data['id'] is None:
                    # cannot retrieve the order, wrong id, no create order, nothing to do
                    self.create_ref_oid = None
                    self.create_oid = None

                    self._entry_state = StrategyTrade.STATE_CANCELED
                else:
                    # exists, do nothing need to retry
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
        if self.position_id:
            # if not accepted as modification do it as limit order
            if trader.modify_position(self.position_id, instrument,
                                      stop_loss_price=self.sl, take_profit_price=limit_price):
                self.tp = limit_price
                self.position_limit = limit_price
                return self.ACCEPTED
            else:
                return self.REJECTED

        return self.NOTHING_TO_DO

    def modify_stop_loss(self, trader: Trader, instrument: Instrument, stop_price: float, hard: bool = True) -> int:
        if self.position_id:
            # if not accepted as modification do it as stop order
            if trader.modify_position(self.position_id, instrument,
                                      stop_loss_price=stop_price, take_profit_price=self.tp):
                self.sl = stop_price
                self.position_stop = stop_price
                return self.ACCEPTED
            else:
                return self.REJECTED

        return self.NOTHING_TO_DO

    def close(self, trader: Trader, instrument: Instrument) -> int:
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

        if self.position_id:
            if trader.close_position(self.position_id, instrument, self.dir, self.position_quantity, True, None):
                self._closing = True
                return self.ACCEPTED
            else:
                return self.REJECTED

        return self.NOTHING_TO_DO

    def reduce(self, trader: Trader, instrument: Instrument, quantity: float) -> int:
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

        if self.position_id:
            # compute the max quantity to reduce
            available_qty = self.e - self.x

            if available_qty > 0.0 and quantity > 0.0:
                reduce_qty = min(quantity, available_qty)

                if trader.close_position(self.position_id, instrument, self.dir, reduce_qty, True, None):
                    # closing only if reduce full qty (because it is same as close)
                    self._closing = quantity >= available_qty
                    return self.ACCEPTED
                else:
                    return self.REJECTED

        return self.NOTHING_TO_DO

    def has_stop_order(self) -> bool:
        return self.position_stop > 0.0

    def has_limit_order(self) -> bool:
        return self.position_limit > 0.0

    def support_both_order(self) -> bool:
        return True

    @classmethod
    def is_margin(cls) -> bool:
        return True

    @classmethod
    def is_spot(cls) -> bool:
        return False

    #
    # signal
    #

    def order_signal(self, signal_type: int, data: dict, ref_order_id: str, instrument: Instrument):
        if signal_type == Signal.SIGNAL_ORDER_OPENED:
            # already get at the return of create_order
            if ref_order_id == self.create_ref_oid:
                self.create_oid = data['id']

                # init created timestamp when create order open
                if not self.eot:
                    self.eot = data['timestamp']

                if data.get('stop-loss'):
                    # self.sl = data['stop-loss']
                    self.position_stop = data['stop-loss']

                if data.get('take-profit'):
                    # self.tp = data['take-profit']
                    self.position_limit = data['take-profit']

                if self.e == 0:  # in case it occurs after position open signal
                    self._entry_state = StrategyTrade.STATE_OPENED

        elif signal_type == Signal.SIGNAL_ORDER_DELETED:
            # create order is no longer active
            if data == self.create_oid:
                self.create_ref_oid = None                
                self.create_oid = None

                if not self.position_id:
                    self._entry_state = StrategyTrade.STATE_DELETED

        elif signal_type == Signal.SIGNAL_ORDER_CANCELED:
            # create order is no longer active
            if data == self.create_oid:
                self.create_ref_oid = None                
                self.create_oid = None

                if not self.position_id:
                    self._entry_state = StrategyTrade.STATE_CANCELED

        elif signal_type == Signal.SIGNAL_ORDER_UPDATED:
            # order price/qty modified, cannot really be used because the strategy might
            # cancel the trade or create another one.
            # for the qty we could have a remaining_qty member, then comparing
            pass  # others updates are done at position signals

        elif signal_type == Signal.SIGNAL_ORDER_TRADED:
            pass  # done at position signals
            # order fully or partially filled
            # filled = 0
            #
            # if data['id'] == self.create_oid or data['id'] == self.position_id:
            #     info = data.get('info', "")
            #
            #     # if info == "closed" or info == "partially-closed":
            #     #     print(data)
            #
            #     if data.get('cumulative-filled') is not None and data['cumulative-filled'] > 0:
            #         filled = data['cumulative-filled'] - self.e  # compute filled qty
            #     elif data.get('filled') is not None and data['filled'] > 0:
            #         filled = data['filled']
            #     else:
            #         filled = 0
            #
            #     # if data.get('avg-price') is not None and data['avg-price'] > 0:
            #     #     # in that case we have avg-price already computed
            #     #     self.aep = data['avg-price']
            #
            #     # elif data.get('exec-price') is not None and data['exec-price'] > 0:
            #     #     # compute the average price
            #     #     self.aep = ((self.aep * self.e) + (data['exec-price'] * filled)) / (self.e + filled)
            #     # else:
            #     #     # no have uses order price
            #     #     self.aep = self.op
            #
            #     # cumulative filled entry qty
            #     # if data.get('cumulative-filled') is not None:
            #     #     self.e = data.get('cumulative-filled')
            #     # elif filled > 0:
            #     #     self.e = instrument.adjust_quantity(self.e + filled)
            #
            #     # if filled > 0:
            #     #     # probably need to update exit orders
            #     #     self._dirty = True
            #
            #     # logger.info("Entry avg-price=%s cum-filled=%s" % (self.aep, self.e))
            #
            #     # if self.e >= self.oq:
            #     #     self._entry_state = StrategyTrade.STATE_FILLED
            #
            #     #     # bitmex does not send ORDER_DELETED signal, cleanup here
            #     #     self.create_oid = None
            #     #     self.create_ref_oid = None
            #     # else:
            #     #     self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED
            #
            #     # # retains the trade timestamp
            #     # if not self._stats['first-realized-entry-timestamp']:
            #     #     self._stats['first-realized-entry-timestamp'] = data.get('timestamp', 0.0)
            #
            #     # self._stats['last-realized-entry-timestamp'] = data.get('timestamp', 0.0)

            # done on position signal
            # if data.get('profit-loss') is not None:
            #     self._stats['unrealized-profit-loss'] = data['profit-loss']
            # if data.get('profit-currency'):
            #     self._stats['profit-loss-currency'] = data['profit-currency']

    def position_signal(self, signal_type: int, data: dict, ref_order_id: str, instrument: Instrument):
        def update_pl():
            # PNL with its currency if provided (useless, computed at update_stats)

            # if data.get('profit-loss') is not None:
            #     self._stats['unrealized-profit-loss'] = data['profit-loss']
            # if data.get('profit-currency'):
            #     self._stats['profit-loss-currency'] = data['profit-currency']

            # realized profit/loss rate
            if self.aep > 0.0 and self.x > 0.0:
                self.pl = self.direction * ((self.axp * self.x) - (self.aep * self.x)) / (self.aep * self.x)

        if signal_type == Signal.SIGNAL_POSITION_OPENED:
            self.position_id = data['id']  # already defined at open

            # init created timestamp when create order open if not defined at open
            if not self.eot:
                self.eot = data.get('timestamp', 0.0)

            if data.get('take-profit'):
                self.position_limit = data['take-profit']

            if data.get('stop-loss'):
                self.position_limit = data['stop-loss']

            if not self.xot and (data.get('take-profit') or data.get('stop-loss')):
                # determine exit order timestamp only if tp or sl defined at open
                self.xot = data['timestamp']

            # current quantity
            if data.get('cumulative-filled') is not None:
                last_qty = data.get('cumulative-filled', 0.0)
            elif data.get('filled') is not None:
                last_qty = data.get('filled', 0.0)
            else:
                last_qty = 0.0

            if last_qty > 0.0:
                # increase entry
                if not self._stats['first-realized-entry-timestamp']:
                    self._stats['first-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                self._stats['last-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                # filled entry quantity from the diff with the previous one (position_quantity might be 0)
                self.e += last_qty - self.position_quantity

                if self.e >= self.oq:
                    self._entry_state = StrategyTrade.STATE_FILLED

                    # entry cannot longer be canceled once fully filled
                    self.create_oid = None
                    self.create_ref_oid = None
                else:
                    self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED

                # keep for close and for delta computation on update
                self.position_quantity = last_qty

                # average entry price at open (simply set)
                if data.get('avg-entry-price') is not None:
                    self.aep = data['avg-entry-price']
                elif data.get('exec-price') is not None:
                    self.aep = data['exec-price']

                update_pl()
            else:
                # in case of a limit order
                self._entry_state = StrategyTrade.STATE_OPENED

        elif signal_type == Signal.SIGNAL_POSITION_UPDATED:
            # update stop_loss/take_profit
            if data.get('take-profit'):
                self.position_limit = data['take-profit']

            if data.get('stop-loss'):
                self.position_stop = data['stop-loss']

            # current quantity
            if data.get('cumulative-filled') is not None:
                last_qty = data.get('cumulative-filled', self.position_quantity)
            elif data.get('filled') is not None:
                last_qty = data.get('filled', 0) + self.position_quantity
            else:
                last_qty = data.get('quantity', self.position_quantity)

            if self.position_quantity != last_qty:
                if last_qty < self.position_quantity:
                    # decrease mean exit
                    if not self._stats['first-realized-exit-timestamp']:
                        self._stats['first-realized-exit-timestamp'] = data.get('timestamp', 0.0)

                    self._stats['last-realized-exit-timestamp'] = data.get('timestamp', 0.0)

                    # filled entry quantity from the diff with the previous one
                    prev_x = self.x
                    self.x += self.position_quantity - last_qty

                    if self.x >= self.e:
                        self._exit_state = StrategyTrade.STATE_FILLED
                    else:
                        self._exit_state = StrategyTrade.STATE_PARTIALLY_FILLED

                    # average exit price at update
                    if data.get('avg-exit-price') is not None:
                        self.axp = data['avg-exit-price']
                    elif data.get('exec-price') is not None:
                        # compute
                        dec_qty = self.position_quantity - last_qty

                        if self.axp:
                            self.axp = (self.axp * prev_x + data['exec-price'] * dec_qty) / (prev_x + dec_qty)
                        else:
                            self.axp = data['exec-price']

                    update_pl()

                elif last_qty > self.position_quantity:
                    # increase mean entry
                    if not self._stats['first-realized-entry-timestamp']:
                        self._stats['first-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                    self._stats['last-realized-entry-timestamp'] = data.get('timestamp', 0.0)

                    # filled entry quantity from the diff with the previous one
                    prev_e = self.e
                    self.e += last_qty - self.position_quantity

                    if self.e >= self.oq:
                        self._entry_state = StrategyTrade.STATE_FILLED

                        # entry cannot longer be canceled once fully filled
                        self.create_oid = None
                        self.create_ref_oid = None
                    else:
                        self._entry_state = StrategyTrade.STATE_PARTIALLY_FILLED

                    # average entry price at update
                    if data.get('avg-entry-price') is not None:
                        self.aep = data['avg-entry-price']
                    elif data.get('exec-price') is not None:
                        # compute
                        inc_qty = last_qty - self.position_quantity

                        if self.aep:
                            self.aep = (self.aep * prev_e + data['exec-price'] * inc_qty) / (prev_e + inc_qty)
                        else:
                            self.aep = data['exec-price']

                    update_pl()

                # keep for close and for delta computation on update
                self.position_quantity = last_qty

        elif signal_type == Signal.SIGNAL_POSITION_DELETED:
            # no longer related position
            self.position_id = None

            # related create order is no longer valid
            self.create_oid = None
            self.create_ref_oid = None

            # filled exit quantity equal to the entry
            prev_x = self.x
            if self.x < self.e:
                dec_qty = self.e - self.x  # realized qty at close
                self.x = self.e
            else:
                dec_qty = 0.0

            self._exit_state = StrategyTrade.STATE_FILLED

            # retains the last trade timestamp
            self._stats['last-realized-exit-timestamp'] = data.get('timestamp', 0.0)

            # average exit price at delete
            if data.get('avg-exit-price') is not None:
                self.axp = data['avg-exit-price']
            elif data.get('exec-price') is not None:
                # compute
                if self.axp:
                    self.axp = (self.axp * prev_x + data['exec-price'] * dec_qty) / (prev_x + dec_qty)
                else:
                    self.axp = data['exec-price']

            # logger.info("Exit avg-price=%s cum-filled=%s" % (self.axp, self.x))

            update_pl()

            # finally empty
            self.position_quantity = 0.0

        elif signal_type == Signal.SIGNAL_POSITION_AMENDED:
            # update stop_loss/take_profit
            if data.get('take-profit'):
                self.position_limit = data['take-profit']

            if data.get('stop-loss'):
                self.position_stop = data['stop-loss']

    def is_target_order(self, order_id: str, ref_order_id: str) -> bool:
        if order_id and (order_id == self.create_oid):
            return True

        if ref_order_id and (ref_order_id == self.create_ref_oid):
            return True

        return False

    def is_target_position(self, position_id: str, ref_order_id: str) -> bool:
        if position_id and (position_id == self.position_id):
            return True

        if ref_order_id and (ref_order_id == self.create_ref_oid):
            return True

        return False

    #
    # persistence
    #

    def dumps(self) -> dict:
        data = super().dumps()

        data['create-ref-oid'] = self.create_ref_oid
        data['create-oid'] = self.create_oid

        data['position-id'] = self.position_id
        data['position-stop'] = self.position_stop
        data['position-limit'] = self.position_limit

        return data

    def loads(self, data: dict, strategy_trader: StrategyTrader) -> bool:
        if not super().loads(data, strategy_trader):
            return False

        self.create_ref_oid = data.get('create-ref-oid')
        self.create_oid = data.get('create-oid')

        self.position_id = data.get('position-id')
        self.position_stop = data.get('position-stop')
        self.position_limit = data.get('position-limit')

        return True

    def check(self, trader: Trader, instrument: Instrument) -> int:
        #
        # order and position
        #

        # entry state
        if self._entry_state in (self.STATE_NEW, self.STATE_REJECTED):
            # never opened, no long exists
            return 0

        position = None
        create_order = None

        if self.position_id:
            position = trader.get_position(self.position_id)

            if not position:
                self.position_id = None

        if self.create_oid or self.create_ref_oid:
            if self.create_oid:
                create_order = trader.get_order(self.create_oid)
            elif self.create_ref_oid:
                create_order = trader.find_order(self.create_ref_oid)

            if not create_order:
                # need to lookup history to know if positions exists/existed
                data = trader.order_info(self.create_oid, instrument)
                # order_history = trader.order_history(self.create_oid, self.create_ref_oid)
                # if order_history:
                #     # @todo compute history, and current state, and retrieve position if still exists
                #     pass

                self.create_oid = None
                self.create_ref_oid = None

        #
        # state consistency
        #

        if self._entry_state in (self.STATE_OPENED, self.STATE_PARTIALLY_FILLED):
            if not create_order or not position:
                # the way to know if filled or canceled is to look order history @todo
                self._entry_state = self.STATE_FILLED

        # exit state
        if self._exit_state == self.STATE_NEW:
            if not position:
                self._exit_state = self.STATE_FILLED

        elif self._exit_state in (self.STATE_OPENED, self.STATE_PARTIALLY_FILLED):
            if not position:
                self._exit_state = self.STATE_FILLED

        elif self._exit_state == self.STATE_FILLED: 
            # was already filled... might not occur but check for it
            return 1  # position or create_order

        # qty/avg price/timestamp update if possible
        # @todo

        return 1  # position or create_order

    #
    # stats
    #

    def update_stats(self, instrument: Instrument, timestamp: float):
        super().update_stats(instrument, timestamp)

        if self.is_active():
            # non realized quantity
            nrq = self.e - self.x

            delta_price = 0.0
            r_delta_price = 0.0

            if self.dir > 0:
                delta_price = instrument.market_bid - self.aep
                r_delta_price = self.axp - self.aep
            elif self.dir < 0:
                delta_price = self.aep - instrument.market_ask
                r_delta_price = self.aep - self.axp

            upnl = nrq * (delta_price / (instrument.one_pip_means or 1.0)) * instrument.value_per_pip
            rpnl = self.x * (r_delta_price / (instrument.one_pip_means or 1.0)) * instrument.value_per_pip
            # upnl = nrq * delta_price * instrument.contract_size  # no have contract size on instrument
            # rpnl = self.x * r_delta_price * instrument.contract_size

            # including fees and realized profit and loss
            self._stats['unrealized-profit-loss'] = instrument.adjust_quote(
                upnl + rpnl - self._stats['entry-fees'] - self._stats['exit-fees'])

    def info_report(self, strategy_trader: StrategyTrader) -> Tuple[str]:
        data = list(super().info_report(strategy_trader))

        if self.create_oid or self.create_ref_oid:
            data.append("Entry order id / ref : %s / %s" % (self.create_oid, self.create_ref_oid))

        if self.position_id:
            data.append("Position id : %s" % (self.position_id,))

        return tuple(data)
