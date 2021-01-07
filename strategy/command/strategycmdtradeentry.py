# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trade entry

from trader.order import Order
from instrument.instrument import Instrument

from strategy.strategyassettrade import StrategyAssetTrade
from strategy.strategymargintrade import StrategyMarginTrade
from strategy.strategypositiontrade import StrategyPositionTrade
from strategy.strategyindmargintrade import StrategyIndMarginTrade

import logging
logger = logging.getLogger('siis.strategy.cmd.tradeentry')
error_logger = logging.getLogger('siis.error.strategy.cmd.tradeentry')


def cmd_trade_entry(strategy, strategy_trader, data):
    """
    Create a new trade according data on given strategy_trader.
    """
    results = {
        'messages': [],
        'error': False
    }

    # command data
    direction = data.get('direction', Order.LONG)
    method = data.get('method', 'market')
    limit_price = data.get('limit-price')
    trigger_price = data.get('trigger-price')
    quantity_rate = data.get('quantity-rate', 1.0)
    stop_loss = data.get('stop-loss', 0.0)
    take_profit = data.get('take-profit', 0.0)
    stop_loss_price_mode = data.get('stop-loss-price-mode', 'price')
    take_profit_price_mode = data.get('take-profit-price-mode', 'price')
    timeframe = data.get('timeframe', Instrument.TF_4HOUR)
    leverage = data.get('leverage', 1.0)
    hedging = data.get('hedging', True)
    margin_trade = data.get('margin-trade', False)
    entry_timeout = data.get('entry-timeout', None)
    context = data.get('context', None)

    if quantity_rate <= 0.0:
        results['messages'].append("Missing or empty quantity.")
        results['error'] = True

    if method not in ('market', 'limit', 'limit-percent', 'trigger', 'best-1', 'best+1', 'best-2', 'best+2'):
        results['messages'].append("Invalid price method (market, limit, limit-percent, trigger, best-1, best+1, best-1, best+2.")
        results['error'] = True

    if method in ('limit', 'limit-percent') and not limit_price:
        results['messages'].append("Limit price or distance is missing.")
        results['error'] = True

    if results['error']:
        return results

    if method == 'market':
        order_type = Order.ORDER_MARKET

    elif method == 'limit':
        order_type = Order.ORDER_LIMIT

    elif method == 'limit-percent':
        order_type = Order.ORDER_LIMIT
        limit_price = strategy_trader.instrument.open_exec_price(direction) * (1.0 - (limit_price * 0.01 * direction))

    elif method == 'trigger':
        order_type = Order.ORDER_STOP

    elif method == 'best-1':
        # limit as first taker price : first ask price in long, first bid price in short
        order_type = Order.ORDER_LIMIT
        limit_price = strategy_trader.instrument.open_exec_price(direction)

    elif method == 'best-2':
        # limit as first maker price + current spread : second ask price in long, second bid price in short
        order_type = Order.ORDER_LIMIT
        limit_price = strategy_trader.instrument.open_exec_price(direction) + strategy_trader.instrument.market_spread * direction

    elif method == 'best+1':
        # limit as first maker price : first bid price in long, first ask price in short
        order_type = Order.ORDER_LIMIT
        limit_price = strategy_trader.instrument.open_exec_price(direction, True)

    elif method == 'best+2':
        # limit as first maker price + current spread : second bid price in long, second ask price in short
        order_type = Order.ORDER_LIMIT
        limit_price = strategy_trader.instrument.open_exec_price(direction, True) - strategy_trader.instrument.market_spread * direction

    else:
        order_type = Order.ORDER_MARKET

    order_quantity = 0.0

    trader = strategy.trader()

    # need a valid price to compute the quantity
    price = limit_price or strategy_trader.instrument.open_exec_price(direction)
    trade = None

    if price <= 0.0:
        results['error'] = True
        results['messages'].append("Price must be greater than zero for %s" % (strategy_trader.instrument.market_id,))
        return results

    if strategy_trader.instrument.has_spot and not margin_trade:
        # market support spot and margin option is not defined
        trade = StrategyAssetTrade(timeframe)

        # adjust max quantity according to free asset of quote, and convert in asset base quantity
        if trader.has_asset(strategy_trader.instrument.quote):
            qty = strategy_trader.instrument.trade_quantity*quantity_rate

            if trader.has_quantity(strategy_trader.instrument.quote, qty):
                order_quantity = strategy_trader.instrument.adjust_quantity(qty / price)  # and adjusted to 0/max/step
            else:
                results['error'] = True
                results['messages'].append("Not enought free quote asset %s, has %s but need %s" % (
                        strategy_trader.instrument.quote,
                        strategy_trader.instrument.format_quantity(trader.asset(strategy_trader.instrument.quote).free),
                        strategy_trader.instrument.format_quantity(qty)))

    elif strategy_trader.instrument.has_margin and strategy_trader.instrument.has_position:
        trade = StrategyPositionTrade(timeframe)

        if strategy_trader.instrument.trade_quantity_mode == Instrument.TRADE_QUANTITY_QUOTE_TO_BASE:
            order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate/price)
        else:
            order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate)

        if not trader.has_margin(strategy_trader.instrument.market_id, order_quantity, price):
            results['error'] = True
            results['messages'].append("Not enought margin, need %s" % (trader.get_needed_margin(strategy_trader.instrument.market_id, order_quantity, price),))

    elif strategy_trader.instrument.has_margin and strategy_trader.instrument.indivisible_position:
        trade = StrategyIndMarginTrade(timeframe)

        if strategy_trader.instrument.trade_quantity_mode == Instrument.TRADE_QUANTITY_QUOTE_TO_BASE:
            order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate/price)
        else:
            order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate)

        if not trader.has_margin(strategy_trader.instrument.market_id, order_quantity, price):
            results['error'] = True
            results['messages'].append("Not enought margin, need %s" % (trader.get_needed_margin(strategy_trader.instrument.market_id, order_quantity, price),))

    elif strategy_trader.instrument.has_margin and not strategy_trader.instrument.indivisible_position and not strategy_trader.instrument.has_position:
        trade = StrategyMarginTrade(timeframe)

        if strategy_trader.instrument.trade_quantity_mode == Instrument.TRADE_QUANTITY_QUOTE_TO_BASE:
            order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate/price)
        else:
            order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate)

        if not trader.has_margin(strategy_trader.instrument.market_id, order_quantity, price):
            results['error'] = True
            results['messages'].append("Not enought margin, need %s" % (trader.get_needed_margin(strategy_trader.instrument.market_id, order_quantity, price),))

    else:
        results['error'] = True
        results['messages'].append("Unsupported market type")

    if order_quantity <= 0 or order_quantity * price < strategy_trader.instrument.min_notional:
        results['error'] = True
        results['messages'].append("Min notional not reached (%s)" % strategy_trader.instrument.min_notional)

    if results['error']:
        return results

    order_price = strategy_trader.instrument.adjust_price(price)

    #
    # compute stop-loss and take-profit price depending of their respective mode
    #

    if stop_loss_price_mode == "percent":
        if direction > 0:
            stop_loss = strategy_trader.instrument.adjust_price(order_price * (1.0 - stop_loss * 0.01))
        elif direction < 0:
            stop_loss = strategy_trader.instrument.adjust_price(order_price * (1.0 + stop_loss * 0.01))

    elif stop_loss_price_mode == "pip":
        if direction > 0:
            stop_loss = strategy_trader.instrument.adjust_price(order_price - stop_loss * strategy_trader.instrument.value_per_pip)
        elif direction < 0:
            stop_loss = strategy_trader.instrument.adjust_price(order_price + stop_loss * strategy_trader.instrument.value_per_pip)

    if take_profit_price_mode == "percent":
        if direction > 0:
            take_profit = strategy_trader.instrument.adjust_price(order_price * (1.0 + take_profit * 0.01))
        elif direction < 0:
            take_profit = strategy_trader.instrument.adjust_price(order_price * (1.0 - take_profit * 0.01))

    elif take_profit_price_mode == "pip":
        if direction > 0:
            take_profit = strategy_trader.instrument.adjust_price(order_price + take_profit * strategy_trader.instrument.value_per_pip)
        elif direction < 0:
            take_profit = strategy_trader.instrument.adjust_price(order_price - take_profit * strategy_trader.instrument.value_per_pip)

    #
    # check stop-loss and take-profit and reject if not consistent
    #

    if stop_loss < 0.0:
        results['error'] = True
        results['messages'].append("Rejected trade on %s:%s because the stop-loss is negative" % (strategy.identifier, strategy_trader.instrument.market_id))

        return results

    if take_profit < 0.0:
        results['error'] = True
        results['messages'].append("Rejected trade on %s:%s because the take-profit is negative" % (strategy.identifier, strategy_trader.instrument.market_id))

        return results

    if direction > 0:
        if stop_loss > 0.0 and stop_loss > order_price:
            results['error'] = True
            results['messages'].append("Rejected trade on %s:%s because the stop-loss is above the entry price" % (strategy.identifier, strategy_trader.instrument.market_id))

            return results

        if take_profit > 0.0 and take_profit < order_price:
            results['error'] = True
            results['messages'].append("Rejected trade on %s:%s because the take-profit is below the entry price" % (strategy.identifier, strategy_trader.instrument.market_id))

            return results

    elif direction < 0:
        if stop_loss > 0.0 and stop_loss < order_price:
            results['error'] = True
            results['messages'].append("Rejected trade on %s:%s because the stop-loss is below the entry price" % (strategy.identifier, strategy_trader.instrument.market_id))

            return results

        if take_profit > 0.0 and take_profit > order_price:
            results['error'] = True
            results['messages'].append("Rejected trade on %s:%s because the take-profit is above the entry price" % (strategy.identifier, strategy_trader.instrument.market_id))

            return results

    if trade:
        # user managed trade
        trade.set_user_trade()

        if entry_timeout:
            # entry timeout expiration defined (could be overrided by trade context if specified)
            trade.entry_timeout = entry_timeout

        if context:
            if not strategy_trader.set_trade_context(trade, context):
                # add an error result message
                results['error'] = True
                results['messages'].append("Rejected trade on %s:%s because the context was not found" % (strategy.identifier, strategy_trader.instrument.market_id))

                return results

        # the new trade must be in the trades list if the event comes before, and removed after only it failed
        strategy_trader.add_trade(trade)

        if trade.open(trader, strategy_trader.instrument, direction, order_type, order_price, order_quantity,
                      take_profit, stop_loss, leverage=leverage, hedging=hedging):

            # notifications and stream
            strategy_trader.notify_trade_entry(strategy.timestamp, trade)

            # add a success result message
            results['messages'].append("Created trade %i on %s:%s" % (trade.id, strategy.identifier, strategy_trader.instrument.market_id))
        else:
            strategy_trader.remove_trade(trade)

            # add an error result message
            results['error'] = True
            results['messages'].append("Rejected trade on %s:%s" % (strategy.identifier, strategy_trader.instrument.market_id))

    return results
