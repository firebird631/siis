# @date 2018-09-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Paper trader, asset spot ordering.

from common.signal import Signal

from trader.position import Position
from trader.order import Order
from trader.asset import Asset

import logging
logger = logging.getLogger('siis.trader.papertrader.asset')


def get_or_add_asset(trader, asset_name, precision=8):
    if asset_name in trader._assets:
        return trader._assets[asset_name]

    asset = Asset(trader, asset_name, precision)
    asset.quote = trader._account.currency

    for k, market in trader._markets.items():
        if market.base == asset_name:
            asset.add_market_id(market.market_id)

            if market.quote == asset.quote:
                # found precision from usual market
                asset.precision = market.size_precision

    trader._assets[asset_name] = asset

    return asset


def exec_buysell_order(trader, order, market, open_exec_price, close_exec_price):
    """
    Execute the order for buy&sell of asset.
    """
    result = False

    trader.lock()

    base_asset = get_or_add_asset(trader, market.base)
    quote_asset = get_or_add_asset(trader, market.quote)

    quote_market = trader._markets.get(quote_asset.symbol+quote_asset.quote)
    quote_exec_price = quote_market.price if quote_market else 1.0

    if order.direction == Position.LONG:
        # buy
        base_qty = order.quantity  # market.adjust_quantity(order.quantity)
        quote_qty = base_qty * open_exec_price  # quote_market.adjust_quantity(base_qty * open_exec_price) if quote_market else trader.adjust_quantity(base_qty * open_exec_price)

        # @todo free quantity
        if not trader._unlimited and quote_qty > quote_asset.quantity:
            trader.unlock()

            # and then rejected order
            trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, trader.name, (
                order.symbol, order.ref_order_id))

            logger.error("Not enough quote asset quantity for %s with %s (have %s)!" % (
                quote_asset.symbol, quote_qty, quote_asset.quantity))

            return Order.REASON_INSUFFICIENT_FUNDS

        # retain the fee on the quote asset
        commission_asset = quote_asset.symbol

        if order.is_market():
            commission_amount = quote_qty * market.taker_fee
        else:
            commission_amount = quote_qty * market.maker_fee

        quote_qty += commission_amount

        # base asset. it will receive its own signal (ignored)
        update_asset(trader, order.order_type, base_asset, market, 0, open_exec_price, base_qty, True, trader.timestamp)
        # quote asset
        update_asset(trader, order.order_type, quote_asset, quote_market, 0, quote_exec_price,
                     quote_qty, False, trader.timestamp)

        # directly executed quantity
        order.executed = base_qty

        # transaction time is current timestamp
        order.transact_time = trader.timestamp

        result = True

        # unlock before notify signals
        trader.unlock()

        #
        # order signal
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

        # signal as watcher service (opened + full traded qty and immediately deleted)
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
            'exec-price': open_exec_price,
            'filled': base_qty,
            'fully-filled': True,
            'cumulative-filled': base_qty,
            'quote-transacted': quote_qty,
            'stop-loss': order.stop_loss,
            'take-profit': order.take_profit,
            'time-in-force': order.time_in_force,
            'commission-amount': commission_amount,
            'commission-asset': commission_asset
        }

        trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_TRADED, trader.name, (
            order.symbol, order_data, order.ref_order_id))
        trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, trader.name, (
            order.symbol, order.order_id, ""))

    elif order.direction == Position.SHORT:
        # sell
        base_qty = order.quantity  # market.adjust_quantity(order.quantity)
        quote_qty = base_qty * close_exec_price  # quote_market.adjust_quantity(base_qty * close_exec_price) if quote_market else trader.adjust_quantity(base_qty * close_exec_price)

        # @todo free quantity
        if not trader._unlimited and base_qty > base_asset.quantity:
            trader.unlock()

            # and then rejected order
            trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_REJECTED, trader.name, (
                order.symbol, order.ref_order_id))

            logger.error("Not enough base asset quantity for %s with %s (have %s)!" % (
                base_asset.symbol, market.format_quantity(base_qty), market.format_quantity(base_asset.quantity)))

            return Order.REASON_INSUFFICIENT_FUNDS

        # retain the fee from the quote asset
        commission_asset = quote_asset.symbol

        if order.is_market():
            commission_amount = quote_qty * market.taker_fee
        else:
            commission_amount = quote_qty * market.maker_fee

        quote_qty -= commission_amount

        # approximation of the profit/loss according to the average price of the base asset
        delta_price = close_exec_price - base_asset.price

        # it will receive its own signal (ignored)
        update_asset(trader, order.order_type, base_asset, market, 0, close_exec_price, base_qty,
                     False, trader.timestamp)
        # quote asset
        position_gain_loss_currency = update_asset(trader, order.order_type, quote_asset, quote_market, 0,
                                                   quote_exec_price, quote_qty, True, trader.timestamp)

        gain_loss_rate = ((close_exec_price - base_asset.price) / base_asset.price) if base_asset.price else 0.0
        position_gain_loss = delta_price * base_qty
        position_gain_loss_currency *= gain_loss_rate

        # directly executed quantity
        order.executed = base_qty

        # transaction time is current timestamp
        order.transact_time = trader.timestamp

        result = True

        # unlock before notify signals
        trader.unlock()

        #
        # order signal
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

        # signal as watcher service (opened + fully traded qty and immediately deleted)
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
            'exec-price': close_exec_price,
            'filled': base_qty,
            'fully-filled': True,
            'cumulative-filled': base_qty,
            'quote-transacted': quote_qty,
            'stop-loss': order.stop_loss,
            'take-profit': order.take_profit,
            'time-in-force': order.time_in_force,
            'commission-amount': commission_amount,
            'commission-asset': commission_asset
        }

        trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_TRADED, trader.name, (
            order.symbol, order_data, order.ref_order_id))
        trader.service.watcher_service.notify(Signal.SIGNAL_ORDER_DELETED, trader.name, (
            order.symbol, order.order_id, ""))

    return Order.REASON_OK if result else Order.REASON_ERROR


def update_asset(trader, order_type, asset, market, trade_id, exec_price, trade_qty, buy_or_sell, timestamp):
    """
    Update asset price and quantity.
    @todo It seems sometime we have a quantity lacking issue.
    """
    curr_price = asset.price  # in asset preferred quote symbol
    curr_qty = asset.quantity

    # base price in quote, time in seconds
    quote_price = 1.0

    if market:
        if asset.symbol != trader._account.currency and market.quote != trader._account.currency:
            # asset is not quote, quote is not default, get its price at trade time
            if trader._watcher:
                if trader._watcher.has_instrument(market.quote+trader._account.currency):
                    # direct, REST call but cost API call and delay
                    quote_price = trader.history_price(market.quote+trader._account.currency, timestamp)
                elif trader._watcher.has_instrument(trader._account.currency+market.quote):
                    # indirect, REST call but cost API call and delay
                    quote_price = 1.0 / trader.history_price(trader._account.currency+market.quote, timestamp)
                else:
                    quote_price = 0.0  # might not occurs
                    logger.warning("Unsupported quote asset " + market.quote)
            else:
                if trader.has_market(market.quote+trader._account.currency):
                    # direct
                    quote_price = trader._markets[market.quote+trader._account.currency].price
                elif trader.has_market(trader._account.currency+market.quote):
                    # indirect
                    quote_price = 1.0 / trader._markets[trader._account.currency+market.quote].price
                else:
                    quote_price = 0.0  # might not occurs
                    logger.warning("Unsupported quote asset " + market.quote)

        price = exec_price * quote_price

        # in quote
        if curr_qty+trade_qty > 0.0:
            if buy_or_sell:
                # adjust price when buying
                curr_price = ((price*trade_qty) + (curr_price*curr_qty)) / (curr_qty+trade_qty)
                curr_price = max(0.0, round(curr_price, market.base_precision))

            curr_qty += trade_qty if buy_or_sell else -trade_qty
            curr_qty = max(0.0, round(curr_qty, market.base_precision))
        else:
            curr_price = 0.0
            curr_qty = 0

        if not curr_price and trade_qty > 0:
            if asset.symbol == trader._account.currency:
                # last min default/alt price
                curr_price = trader.history_price(asset.symbol+trader.account.alt_currency, timestamp)
            else:
                if trader._watcher:
                    # base price in quote at trade time
                    if trader._watcher.has_instrument(asset.symbol+trader._account.currency):
                        # direct
                        curr_price = trader.history_price(asset.symbol+trader._account.currency, timestamp)
                    elif trader._watcher.has_instrument(trader._account.currency+asset.symbol):
                        # indirect
                        curr_price = 1.0 / trader.history_price(trader._account.currency+asset.symbol, timestamp)
                    else:
                        curr_price = 0.0  # might not occurs
                        logger.warning("Unsupported asset " + asset.symbol)
                else:
                    if trader.has_market(asset.symbol+trader._account.currency):
                        # direct
                        curr_price = trader._markets[asset.symbol+trader._account.currency].price
                    elif trader.has_market(trader._account.currency+asset.symbol):
                        # indirect
                        quote_price = 1.0 / trader._markets[trader._account.currency+asset.symbol].price
                    else:
                        quote_price = 0.0  # might not occurs
                        logger.warning("Unsupported quote asset " + market.quote)

        # update price
        asset.update_price(timestamp, trade_id, curr_price, asset.quote)

    # update qty
    if buy_or_sell:
        # more free
        asset.set_quantity(asset.locked, asset.free+trade_qty)
    else:
        # less free @todo manage locked part for limit orders
        asset.set_quantity(0.0, max(0.0, asset.quantity-trade_qty))
        # if order_type in (Order.ORDER_MARKET, Order.ORDER_STOP, Order.ORDER_TAKE_PROFIT):
        #   # taker, less free
        #   asset.set_quantity(asset.locked, max(0.0, asset.free-trade_qty)) 
        # else:
        #   # maket, less locked
        #   asset.set_quantity(max(0.0, asset.locked-trade_qty), asset.free)

    # update profit/loss
    if market:
        asset.update_profit_loss(market)

    return quote_price * trade_qty
