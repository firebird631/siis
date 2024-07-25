# @date 2018-09-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Paper trader, indivisible margin ordering/position.

from common.signal import Signal

from trader.position import Position
from trader.order import Order

import logging
logger = logging.getLogger('siis.trader.papertrader.indmargin')


def exec_indmargin_order(trader, order, market, open_exec_price: float, close_exec_price: float):
    """
    Execute the order for indivisible margin position.
    @note No hedging possible.
    @note Must be mutex locked.
    @note If hedging there must be two distinct positions identifiers (+BTCUSDT or -BTCUSDT for example)
    @todo update to support only indivisible margin order
    @todo partial reduce position (avg exit price, qty of position)
    @warning commission amount cannot be correct if commission/settlement currency is not stable (contract size missing)
    """
    current_position = None

    trader.lock()

    if order.symbol:
        # in that case position is identifier by its market
        current_position = trader._positions.get(order.symbol)

    if current_position and current_position.is_opened():
        # in base currency
        position_gain_loss = 0.0

        if order.direction == current_position.direction:
            # first, same direction, increase the position
            realized_position_cost = market.effective_cost(order.quantity, open_exec_price)
            margin_cost = market.margin_cost(order.quantity, open_exec_price)

            if not trader._unlimited and trader.account.margin_balance < margin_cost:
                # and then rejected order
                trader.unlock()

                trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, trader.name, (
                    order.symbol, order.ref_order_id))

                logger.error("Not enough free margin for %s need %s but have %s!" % (
                    order.symbol, margin_cost, trader.account.margin_balance))

                return Order.REASON_INSUFFICIENT_MARGIN

            # still in long, position size increase and adjust the entry price
            entry_price = ((current_position.entry_price * current_position.quantity) + (
                    open_exec_price * order.quantity)) / (current_position.quantity + order.quantity)

            current_position.entry_price = entry_price
            current_position.quantity += order.quantity

            # directly executed quantity
            order.executed = order.quantity
            exec_price = open_exec_price

            # increase used margin
            trader.account.use_margin(margin_cost)
        else:
            # opposite direction
            if current_position.quantity > order.quantity:
                # first case the direction still the same, reduce the position and the margin
                # take the profit/loss from the difference by order.quantity and adjust the entry price and quantity
                position_gain_loss = market.compute_pnl(order.quantity, current_position.direction,
                                                        current_position.entry_price, close_exec_price)

                realized_position_cost = market.effective_cost(order.quantity, close_exec_price)
                margin_cost = market.margin_cost(order.quantity, close_exec_price)

                # and decrease used margin
                trader.account.free_margin(margin_cost)

                # average position entry price does not move because only reduce
                current_position.quantity -= order.quantity
                exec_price = close_exec_price

                # directly executed quantity
                order.executed = order.quantity

            elif current_position.quantity == order.quantity:
                # second case the position is closed, exact quantity in the opposite direction
                position_gain_loss = market.compute_pnl(order.quantity, current_position.direction,
                                                        current_position.entry_price, close_exec_price)

                realized_position_cost = market.effective_cost(order.quantity, close_exec_price)
                margin_cost = market.margin_cost(order.quantity, close_exec_price)

                # average position entry price does not move because only reduce
                # directly executed quantity
                current_position.quantity = 0.0
                order.executed = order.quantity
                exec_price = close_exec_price

                # and decrease used margin
                trader.account.free_margin(margin_cost)
            else:
                # third case the position is reversed
                # 1) get the profit/loss
                position_gain_loss = market.compute_pnl(current_position.quantity, current_position.direction,
                                                        current_position.entry_price, close_exec_price)

                realized_position_cost = market.effective_cost(current_position.quantity, close_exec_price)
                margin_cost = market.margin_cost(current_position.quantity, close_exec_price)

                # first decrease of released margin
                trader.account.free_margin(margin_cost)

                # 2) adjust the position entry, average position is based on the open exec price
                current_position.quantity = order.quantity - current_position.quantity
                current_position.entry_price = open_exec_price

                # 3) the direction is now at opposite
                current_position.direction = order.direction

                # directly executed quantity
                order.executed = order.quantity
                exec_price = open_exec_price

                margin_cost = market.margin_cost(order.quantity-current_position.quantity, open_exec_price)

                # next increase margin of the new volume
                trader.account.use_margin(margin_cost)

        # transaction time is current timestamp
        order.transact_time = trader.timestamp
        # order.set_position_id(current_position.position_id)

        if position_gain_loss != 0.0 and realized_position_cost > 0.0:
            # compute position rates
            raw_gain_loss_rate = position_gain_loss / realized_position_cost

            # if maker close (limit+post-order) @todo estimate fees
            current_position.profit_loss = position_gain_loss
            current_position.profit_loss_rate = raw_gain_loss_rate

            # if taker close (market) @todo estimate fees
            current_position.profit_loss_market = position_gain_loss
            current_position.profit_loss_market_rate = raw_gain_loss_rate

            trader.account.add_realized_profit_loss(position_gain_loss / market.base_exchange_rate)

        # retain the fee on the account currency
        commission_asset = trader.account.currency

        if order.is_market():
            commission_amount = realized_position_cost * market.taker_fee + market.taker_commission
        else:
            commission_amount = realized_position_cost * market.maker_fee + market.maker_commission

        # fees are realized loss
        trader.account.use_balance(commission_amount / market.base_exchange_rate)

        # unlock before notify signals
        trader.unlock()

        result = True

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
        trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_OPENED, trader.name, (
            order.symbol, order_data, order.ref_order_id))

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
            'avg-price': exec_price,  # current_position.entry_price,
            'filled': order.executed,
            'cumulative-filled': order.executed,
            'quote-transacted': realized_position_cost,  # its margin
            'stop-loss': order.stop_loss,
            'take-profit': order.take_profit,
            'time-in-force': order.time_in_force,
            # 'commission-amount': commission_amount,
            # 'commission-asset': commission_asset
        }

        trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_TRADED, trader.name, (
            order.symbol, order_data, order.ref_order_id))

        #
        # position signal
        #

        # signal as watcher service
        if current_position.quantity <= 0:
            # closed position
            position_data = {
                'id': current_position.position_id,
                'symbol': current_position.symbol,
                'direction': current_position.direction,
                'timestamp': order.transact_time,
                'quantity': 0,
                'exec-price': exec_price,
                'stop-loss': None,
                'take-profit': None
            }

            trader.service.watcher_service.notify(Signal.SIGNAL_POSITION_DELETED, trader.name, (
                order.symbol, position_data, order.ref_order_id))
        else:
            # updated position
            position_data = {
                'id': current_position.position_id,
                'symbol': current_position.symbol,
                'direction': current_position.direction,
                'timestamp': order.transact_time,
                'quantity': current_position.quantity,
                # 'avg-entry-price': current_position.entry_price,
                # 'avg-exit-price': current_position.exit_price,
                'exec-price': exec_price,
                'stop-loss': current_position.stop_loss,
                'take-profit': current_position.take_profit,
                # 'profit-loss': @todo here
            }

            trader.service.watcher_service.notify(Signal.SIGNAL_POSITION_UPDATED, trader.name, (
                order.symbol, position_data, order.ref_order_id))

        # and then deleted order
        trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, trader.name, (
            order.symbol, order.order_id, ""))

        # if position is empty -> closed -> delete it
        if current_position.quantity <= 0.0:
            # take care this does not make an issue
            current_position.exit(exec_price)
    else:
        # unique position per market
        position_id = market.market_id

        realized_position_cost = market.effective_cost(order.quantity, open_exec_price)
        margin_cost = market.margin_cost(order.quantity, open_exec_price)

        if not trader._unlimited and trader.account.margin_balance < margin_cost:
            # and then rejected order
            trader.unlock()

            trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, trader.name, (
                order.symbol, order.ref_order_id))

            logger.error("Not enough free margin for %s need %s but have %s!" % (
                order.symbol, margin_cost, trader.account.margin_balance))

            return Order.REASON_INSUFFICIENT_MARGIN

        # create a new position at market
        position = Position(trader)
        position.symbol = order.symbol

        position.set_position_id(position_id)
        position.set_key(trader.service.gen_key())

        position.entry(order.direction, order.symbol, order.quantity)
        position.leverage = order.leverage

        position.created_time = trader.timestamp

        # long are open on ask and short on bid
        exec_price = open_exec_price
        position.entry_price = exec_price
        # logger.debug("%s %f %f %f %i" % ("el" if position.direction>0 else "es",
        #     position.entry_price, market.bid, market.ask, market.bid < market.ask))

        # transaction time is creation position date time
        order.transact_time = position.created_time
        order.set_position_id(position_id)

        # directly executed quantity
        order.executed = order.quantity

        trader._positions[position_id] = position

        # increase used margin
        trader.account.use_margin(margin_cost)

        # retain the fee on the account currency
        commission_asset = trader.account.currency

        if order.is_market():
            commission_amount = realized_position_cost * market.taker_fee + market.taker_commission
        else:
            commission_amount = realized_position_cost * market.maker_fee + market.maker_commission

        # fees are realized loss
        trader.account.use_balance(commission_amount / market.base_exchange_rate)

        # unlock before notify signals
        trader.unlock()

        result = True

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
        trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_OPENED, trader.name, (
            order.symbol, order_data, order.ref_order_id))

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
            # 'commission-amount': commission_amount,
            # 'commission-asset': commission_asset
        }

        # logger.info("%s %s %s" % (position.entry_price, position.quantity, order.direction))
        trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_TRADED, trader.name, (
            order.symbol, order_data, order.ref_order_id))

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
            'take-profit': position.take_profit
        }

        # signal as watcher service (position opened fully completed)
        trader.service.watcher_service.notify(Signal.SIGNAL_POSITION_OPENED, trader.name, (
            order.symbol, position_data, order.ref_order_id))

        # and then deleted order
        trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, trader.name, (
            order.symbol, order.order_id, ""))

    return Order.REASON_OK if result else Order.REASON_ERROR
