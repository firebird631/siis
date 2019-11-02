# @date 2018-09-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Paper trader, margin ordering/postion.

import base64
import uuid

from datetime import datetime

from common.signal import Signal

from trader.position import Position
from trader.order import Order
from terminal.terminal import Terminal

from .papertraderhistory import PaperTraderHistory, PaperTraderHistoryEntry

import logging
logger = logging.getLogger('siis.trader.papertrader.margin')


def exec_margin_order(trader, order, market, open_exec_price, close_exec_price):
    """
    Execute the order for margin position.
    @todo support of hedging else reduce first the opposite direction positions (FIFO method)
    """
    current_position = None
    positions = []

    trader.lock()

    if order.position_id:
        current_position = trader._positions.get(order.position_id)
    else:
        # @todo
        pass
        # # position of the same market on any directions
        # for k, pos in trader._positions.items():
        #     if pos.symbol == order.symbol:
        #         positions.append(pos)

        # if order.hedging and market.hedging:
        #     pass
        # else:
        #     current_position = positions[-1] if positions else None

    if current_position and current_position.is_opened():
        # increase or reduce the current position
        org_quantity = current_position.quantity
        exec_price = 0.0

        #
        # and adjust the position quantity (no hedging)
        #

        # price difference depending of the direction
        delta_price = 0
        if current_position.direction == Position.LONG:
            delta_price = close_exec_price - current_position.entry_price
            # logger.debug("cl", delta_price, " use ", close_exec_price, " other ", open_exec_price, close_exec_price < open_exec_price)
        elif current_position.direction == Position.SHORT:
            delta_price = current_position.entry_price - close_exec_price
            # logger.debug("cs", delta_price, " use ", close_exec_price, " other ", open_exec_price, close_exec_price < open_exec_price)

        # keep for percent calculation
        prev_entry_price = current_position.entry_price or close_exec_price
        leverage = order.leverage

        # most of thoose data rarely change except the base_exchange_rate
        value_per_pip = market.value_per_pip
        contract_size = market.contract_size
        lot_size = market.lot_size
        one_pip_means = market.one_pip_means
        base_exchange_rate = market.base_exchange_rate
        margin_factor = market.margin_factor

        # logger.debug(order.symbol, bid_price, ofr_price, open_exec_price, close_exec_price, delta_price, current_position.entry_price, order.price)
        realized_position_cost = 0.0  # realized cost of the position in base currency

        # effective meaning of delta price in base currency
        effective_price = (delta_price / one_pip_means) * value_per_pip

        # in base currency
        position_gain_loss = 0.0

        if order.direction == current_position.direction:
            # first, same direction, increase the position
            realized_position_cost = market.effective_cost(order.quantity, open_exec_price)
            margin_cost = market.margin_cost(order.quantity, open_exec_price)

            if not trader._unlimited and trader.account.margin_balance < margin_cost:
                # and then rejected order
                trader.unlock()

                trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, trader.name, (order.symbol, order.ref_order_id))

                logger.error("Not enought free margin for %s need %s but have %s!" % (order.symbol, margin_cost, trader.account.margin_balance))
                return False

            # still in long, position size increase and adjust the entry price
            entry_price = ((current_position.entry_price * current_position.quantity) + (open_exec_price * order.quantity)) / 2
            current_position.entry_price = entry_price
            current_position.quantity += order.quantity

            # directly executed quantity
            order.executed = order.quantity
            exec_price = open_exec_price

            # increase used margin
            trader.account.use_margin(margin_cost)
        else:
            # different direction
            if current_position.quantity > order.quantity:
                # first case the direction still the same, reduce the position and the margin
                # take the profit/loss from the difference by order.quantity and adjust the entry price and quantity
                position_gain_loss = effective_price * order.quantity

                realized_position_cost = market.effective_cost(order.quantity, close_exec_price)
                margin_cost = market.margin_cost(order.quantity, close_exec_price)

                # and decrease used margin
                trader.account.free_margin(margin_cost)

                # entry price might not move...
                # current_position.entry_price = ((current_position.entry_price * current_position.quantity) - (close_exec_price * order.quantity)) / 2
                current_position.quantity -= order.quantity
                current_position.exit_price = close_exec_price

                exec_price = close_exec_price

                # directly executed quantity
                order.executed = order.quantity

            elif current_position.quantity == order.quantity:
                # second case the position is closed, exact quantity in the opposite direction
                position_gain_loss = effective_price * current_position.quantity

                current_position.quantity = 0.0
                current_position.exit_price = close_exec_price

                realized_position_cost = market.effective_cost(order.quantity, close_exec_price)
                margin_cost = market.margin_cost(order.quantity, close_exec_price)

                # directly executed quantity
                order.executed = order.quantity
                exec_price = close_exec_price

                # and decrease used margin
                trader.account.free_margin(margin_cost)
            else:
                # third case the position is reversed
                # 1) get the profit loss
                position_gain_loss = effective_price * current_position.quantity

                realized_position_cost = market.effective_cost(order.quantity, close_exec_price)
                margin_cost = market.margin_cost(order.quantity, close_exec_price)

                # first decrease of released margin
                trader.account.free_margin(margin_cost)

                # 2) adjust the position entry
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

        #order.set_position_id(current_position.position_id)

        if position_gain_loss != 0.0 and realized_position_cost > 0.0:
            # ratio
            gain_loss_rate = position_gain_loss / realized_position_cost
            relative_gain_loss_rate = delta_price / prev_entry_price

            # if maker close (limit+post-order) (for now same as market)
            current_position.profit_loss = position_gain_loss
            current_position.profit_loss_rate = gain_loss_rate

            # if taker close (market)
            current_position.profit_loss_market = position_gain_loss
            current_position.profit_loss_market_rate = gain_loss_rate

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

        #
        # history
        #

        if trader._history:
            # and keep for history (backtesting reporting)
            history = PaperTraderHistoryEntry(order,
                    trader.account.balance, trader.account.margin_balance, delta_price/one_pip_means,
                    gain_loss_rate, position_gain_loss, position_gain_loss/base_exchange_rate)

            trader._history.add(history)

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
            'avg-price': current_position.entry_price,
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

        # signal as watcher service
        if current_position.quantity <= 0:
            # closed position
            position_data = {
                'id': current_position.position_id,
                'symbol': current_position.symbol,
                'direction': current_position.direction,
                'timestamp': order.transact_time,
                'quantity': 0,
                'avg-entry-price': current_position.entry_price,
                'avg-exit-price': current_position.exit_price,
                'exec-price': exec_price,
                'stop-loss': None,
                'take-profit': None,
                'profit-loss': current_position.profit_loss,
                'profit-loss-currency': market.quote
            }

            trader.service.watcher_service.notify(Signal.SIGNAL_POSITION_DELETED, trader.name, (order.symbol, position_data, order.ref_order_id))
        else:
            # updated position
            position_data = {
                'id': current_position.position_id,
                'symbol': current_position.symbol,
                'direction': current_position.direction,
                'timestamp': order.transact_time,
                'quantity': current_position.quantity,
                'avg-entry-price': current_position.entry_price,
                'avg-exit-price': current_position.exit_price,
                'exec-price': exec_price,
                'stop-loss': current_position.stop_loss,
                'take-profit': current_position.take_profit,
                'profit-loss': current_position.profit_loss,
                'profit-loss-currency': market.quote
            }

            trader.service.watcher_service.notify(Signal.SIGNAL_POSITION_UPDATED, trader.name, (order.symbol, position_data, order.ref_order_id))

        # and then deleted order
        trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, trader.name, (order.symbol, order.order_id, ""))

        # if position is empty -> closed -> delete it
        if current_position.quantity <= 0.0:
            current_position.exit(None)

            # done during next update
            # trader.lock()

            # if current_position.position_id in trader._positions:
            #     del trader._positions[current_position.position_id]

            # trader.unlock()
    else:
        # get a new distinct position id
        position_id = "siis_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n')

        realized_position_cost = market.effective_cost(order.quantity, open_exec_price)
        margin_cost = market.margin_cost(order.quantity, open_exec_price)

        if not trader._unlimited and trader.account.margin_balance < margin_cost:
            # and then rejected order
            trader.unlock()

            trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, trader.name, (order.symbol, order.ref_order_id))

            logger.error("Not enought free margin for %s need %s but have %s!" % (order.symbol, margin_cost, trader.account.margin_balance))
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
        # logger.debug("%s %f %f %f %i" % ("el" if position.direction>0 else "es", position.entry_price, market.bid, market.ofr, market.bid < market.ofr))

        # transaction time is creation position date time
        order.transact_time = position.created_time
        order.set_position_id(position_id)

        # directly executed quantity
        order.executed = order.quantity

        trader._positions[position_id] = position

        # increase used margin
        trader.account.use_margin(margin_cost)

        #
        # history
        #

        if trader._history:
            history = PaperTraderHistoryEntry(order, trader.account.balance, trader.account.margin_balance)
            trader._history.add(history)

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

        #logger.info("%s %s %s" % (position.entry_price, position.quantity, order.direction))
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

    return result
