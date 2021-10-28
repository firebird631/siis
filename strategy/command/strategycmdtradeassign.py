# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trade assign

from trader.order import Order
from instrument.instrument import Instrument

from strategy.strategyassettrade import StrategyAssetTrade
from strategy.strategymargintrade import StrategyMarginTrade
from strategy.strategypositiontrade import StrategyPositionTrade
from strategy.strategyindmargintrade import StrategyIndMarginTrade


def cmd_trade_assign(strategy, strategy_trader, data):
    """
    Assign a free quantity of an asset to a newly created trade according data on given strategy_trader.

    @todo Support for margin, ind-margin, position trade and short.
    @todo Support for order-type else assume LIMIT.
    """
    results = {
        'messages': [],
        'error': False
    }

    # command data
    direction = data.get('direction', Order.LONG)
    entry_price = data.get('entry-price', 0.0)
    quantity = data.get('quantity', 0.0)
    stop_loss = data.get('stop-loss', 0.0)
    take_profit = data.get('take-profit', 0.0)
    timeframe = data.get('timeframe', Instrument.TF_4HOUR)
    context = data.get('context', None)
    order_type = data.get('order-type', Order.ORDER_LIMIT)

    if quantity <= 0.0:
        results['messages'].append("Missing or empty quantity.")
        results['error'] = True

    if entry_price <= 0:
        results['messages'].append("Invalid entry price.")
        results['error'] = True

    if stop_loss:
        if direction > 0 and stop_loss >= entry_price:
            results['messages'].append("Stop-loss price must be lesser than entry price.")
            results['error'] = True
        elif direction < 0 and stop_loss <= entry_price:
            results['messages'].append("Stop-loss price must be greater than entry price.")
            results['error'] = True

    if take_profit:
        if direction > 0 and take_profit <= entry_price:
            results['messages'].append("Take-profit price must be greater then entry price.")
            results['error'] = True
        elif direction < 0 and take_profit >= entry_price:
            results['messages'].append("Take-profit price must be lesser then entry price.")
            results['error'] = True

    if direction != Order.LONG and direction != Order.SHORT:
        results['messages'].append("Invalid direction.")
        results['error'] = True

    if direction != Order.LONG:
        results['messages'].append("Only trade long direction is allowed.")
        results['error'] = True

    trader = strategy.trader()

    if not trader.has_quantity(strategy_trader.instrument.base, quantity):
        results['messages'].append("No enough free asset quantity.")
        results['error'] = True

    # @todo others trade models
    if not strategy_trader.instrument.has_spot:
        results['messages'].append("Only allowed on a spot market.")
        results['error'] = True

    if results['error']:
        return results

    trade = StrategyAssetTrade(timeframe)

    trade.assign(trader, strategy_trader.instrument, direction, order_type,
                 entry_price, quantity, take_profit, stop_loss)

    if context:
        if not strategy_trader.set_trade_context(trade, context):
            # add an error result message
            results['error'] = True
            results['messages'].append("Rejected trade on %s:%s because the context was not found" % (
                strategy.identifier, strategy_trader.instrument.market_id))

            return results

    strategy_trader.add_trade(trade)

    # update strategy-trader
    strategy.send_update_strategy_trader(strategy_trader.instrument.market_id)

    # update stats
    trade.update_stats(strategy_trader.instrument, strategy.timestamp)

    results['messages'].append("Assigned trade %i on %s:%s" % (
        trade.id, strategy.identifier, strategy_trader.instrument.market_id))

    return results
