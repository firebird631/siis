# @date 2018-09-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Paper trader, margin position management

import base64
import uuid

from datetime import datetime

from common.signal import Signal

from trader.position import Position
from trader.order import Order
from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.trader.papertrader.position')


def open_position(trader, order, market, open_exec_price):
    """
    Execute the order for margin position.
    """
    current_position = None
    positions = []

    trader.lock()

    # get a new distinct position id
    position_id = "siis_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n')

    realized_position_cost = market.effective_cost(order.quantity, open_exec_price)
    margin_cost = market.margin_cost(order.quantity, open_exec_price)

    if not trader._unlimited and trader.account.margin_balance < margin_cost:
        # and then rejected order
        trader.unlock()

        logger.error("Not enought free margin for %s need %s but have %s!" % (order.symbol, margin_cost, trader.account.margin_balance))
        trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, trader.name, (order.symbol, order.ref_order_id))

        return False

    # create a new position at market
    position = Position(trader)
    position.symbol = order.symbol

    position.set_position_id(position_id)
    position.set_key(trader.service.gen_key())

    position.entry(order.direction, order.symbol, order.quantity)
    position.leverage = order.leverage

    position.created_time = trader.timestamp

    account_currency = trader.account.currency

    # long are open on ofr and short on bid
    position.entry_price = market.open_exec_price(order.direction)

    # transaction time is creation position date time
    order.transact_time = position.created_time
    order.set_position_id(position_id)

    # directly executed quantity
    order.executed = order.quantity

    trader._positions[position_id] = position

    # increase used margin
    trader.account.use_margin(margin_cost)

    # unlock before notify signals
    trader.unlock()

    #
    # order signal (SIGNAL_ORDER_OPENED+TRADED+DELETED, fully completed)
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

    # signal as watcher service (opened + fully traded qty)
    trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_OPENED, trader.name, (order.symbol, order_data, order.ref_order_id))

    order_data = {
        'id': order.order_id,
        'symbol': order.symbol,
        'type': order.order_type,
        'trade-id': 0,
        'direction': order.direction,
        'timestamp': order.transact_time,
        'quantity': order.quantity,
        'price': order.price,
        'stop-price': order.stop_price,
        'exec-price': position.entry_price,
        'avg-price': position.entry_price,
        'filled': order.executed,
        'cumulative-filled': order.executed,
        'quote-transacted': realized_position_cost,  # its margin
        'stop-loss': order.stop_loss,
        'take-profit': order.take_profit,
        'time-in-force': order.time_in_force,
        'commission-amount': 0,  # @todo
        'commission-asset': trader.account.currency
    }

    trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_TRADED, trader.name, (order.symbol, order_data, order.ref_order_id))

    #
    # position signal
    #

    position_data = {
        'id': position.position_id,
        'symbol': position.symbol,
        'direction': position.direction,
        'timestamp': order.transact_time,
        'quantity': position.quantity,
        'exec-price': position.entry_price,
        'stop-loss': position.stop_loss,
        'take-profit': position.take_profit,
        'avg-entry-price': position.entry_price,
        'profit-loss': 0.0,
        'profit-loss-currency': market.quote
    }

    # signal as watcher service (position opened fully completed)
    trader.service.watcher_service.notify(Signal.SIGNAL_POSITION_OPENED, trader.name, (order.symbol, position_data, order.ref_order_id))

    # and then deleted order
    trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, trader.name, (order.symbol, order.order_id, ""))

    return True


def close_position(trader, market, position, close_exec_price, order_type=Order.ORDER_LIMIT):
    """
    Close a position.
    """
    if not position:
        return False

    trader.lock()

    if not position.is_opened():
        trader.unlock()
        return False

    # create an order for the close
    order = Order(trader, position.symbol)
    order.set_position_id(position.position_id)

    order.direction = position.close_direction()
    order.order_type = order_type

    if order_type == Order.ORDER_LIMIT:
        order.price = close_exec_price

    order.quantity = position.quantity
    order.leverage = position.leverage

    order.close_only = True
    order.reduce_only = True

    # increase or reduce the current position
    org_quantity = position.quantity
    exec_price = 0.0

    # price difference depending of the direction
    delta_price = 0
    if position.direction == Position.LONG:
        delta_price = close_exec_price - position.entry_price
    elif position.direction == Position.SHORT:
        delta_price = position.entry_price - close_exec_price

    # keep for percent calculation
    prev_entry_price = position.entry_price or close_exec_price
    leverage = order.leverage

    # most of thoose data rarely change except the base_exchange_rate
    value_per_pip = market.value_per_pip
    contract_size = market.contract_size
    lot_size = market.lot_size
    one_pip_means = market.one_pip_means
    base_exchange_rate = market.base_exchange_rate
    margin_factor = market.margin_factor

    realized_position_cost = 0.0  # realized cost of the position in base currency

    # effective meaning of delta price in base currency
    effective_price = (delta_price / one_pip_means) * value_per_pip

    # in base currency
    position_gain_loss = 0.0

    # the position is closed, exact quantity in the opposite direction
    position_gain_loss = effective_price * position.quantity
    position.quantity = 0.0
    position.exit_price = close_exec_price

    # directly executed quantity
    order.executed = order.quantity
    exec_price = close_exec_price

    realized_position_cost = market.effective_cost(order.quantity, close_exec_price)
    margin_cost = market.margin_cost(order.quantity, close_exec_price)

    # and decrease used margin
    trader.account.free_margin(margin_cost)

    # transaction time is current timestamp
    order.transact_time = trader.timestamp

    if position_gain_loss != 0.0 and realized_position_cost > 0.0:
        # ratio
        gain_loss_rate = position_gain_loss / realized_position_cost
        relative_gain_loss_rate = delta_price / prev_entry_price

        # if maker close (limit+post-order) (for now same as market)
        position.profit_loss = position_gain_loss
        position.profit_loss_rate = gain_loss_rate

        # if taker close (market)
        position.profit_loss_market = position_gain_loss
        position.profit_loss_market_rate = gain_loss_rate

        trader.account.add_realized_profit_loss(position_gain_loss / base_exchange_rate)

        # display only for debug
        if position_gain_loss > 0.0:
            Terminal.inst().high("Close profitable position with %.2f on %s (%.2fpips) (%.2f%%) at %s" % (
                position_gain_loss, order.symbol, delta_price/one_pip_means, gain_loss_rate*100.0, market.format_price(close_exec_price)), view='debug')
        elif position_gain_loss < 0.0:
            Terminal.inst().low("Close loosing position with %.2f on %s (%.2fpips) (%.2f%%) at %s" % (
                position_gain_loss, order.symbol, delta_price/one_pip_means, gain_loss_rate*100.0, market.format_price(close_exec_price)), view='debug')
    else:
        gain_loss_rate = 0.0

    # unlock before notify signals
    trader.unlock()

    #
    # order signal (SIGNAL_ORDER_OPENED+DELETED because we assume fully completed)
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

    # signal as watcher service (opened + fully traded qty)
    trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_OPENED, trader.name, (order.symbol, order_data, order.ref_order_id))

    order_data = {
        'id': order.order_id,
        'symbol': order.symbol,
        'type': order.order_type,
        'trade-id': 0,
        'direction': order.direction,
        'timestamp': order.transact_time,
        'quantity': order.quantity,
        'price': order.price,
        'stop-price': order.stop_price,
        'exec-price': exec_price,
        'avg-price': position.entry_price,
        'filled': order.executed,
        'cumulative-filled': order.executed,
        'quote-transacted': realized_position_cost,  # its margin
        'stop-loss': order.stop_loss,
        'take-profit': order.take_profit,
        'time-in-force': order.time_in_force,
        'commission-amount': 0,
        'commission-asset': trader.account.currency
    }

    trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_TRADED, trader.name, (order.symbol, order_data, order.ref_order_id))

    #
    # position signal
    #

    # closed position
    position_data = {
        'id': position.position_id,
        'symbol': position.symbol,
        'direction': position.direction,
        'timestamp': order.transact_time,
        'quantity': 0,
        'avg-entry-price': position.entry_price,
        'avg-exit-price': position.exit_price,
        'exec-price': exec_price,
        'stop-loss': None,
        'take-profit': None,
        'profit-loss': position.profit_loss,
        'profit-loss-currency': market.quote
    }

    trader.service.watcher_service.notify(Signal.SIGNAL_POSITION_DELETED, trader.name, (order.symbol, position_data, order.ref_order_id))

    # and then deleted order
    trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, trader.name, (order.symbol, order.order_id, ""))

    position.exit(exec_price)

    return True
