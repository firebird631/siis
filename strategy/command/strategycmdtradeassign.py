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

    if quantity <= 0.0:
        results['messages'].append("Missing or empty quantity.")
        results['error'] = True

    if entry_price <= 0:
        results['messages'].append("Invalid entry price.")
        results['error'] = True

    if stop_loss and stop_loss > entry_price:
        results['messages'].append("Stop-loss price must be lesser than entry price.")
        results['error'] = True

    if take_profit and take_profit < entry_price:
        results['messages'].append("Take-profit price must be greater then entry price.")
        results['error'] = True

    if direction != Order.LONG:
        results['messages'].append("Only trade long direction is allowed.")
        results['error'] = True

    trader = strategy.trader()

    if not trader.has_quantity(strategy_trader.instrument.base, quantity):
        results['messages'].append("No enought free asset quantity.")
        results['error'] = True

    # @todo trade type
    if not strategy_trader.instrument.has_spot:
        results['messages'].append("Only allowed on a spot market.")
        results['error'] = True

    if results['error']:
        return results

    trade = StrategyAssetTrade(timeframe)

    # user managed trade
    trade.set_user_trade()

    trade._entry_state = StrategyAssetTrade.STATE_FILLED
    trade._exit_state = StrategyAssetTrade.STATE_NEW
    
    trade.dir = Order.LONG
    trade.op = entry_price
    trade.oq = quantity

    trade.tp = take_profit
    trade.sl = stop_loss        

    trade.eot = strategy.timestamp

    trade.aep = entry_price

    trade.e = quantity

    strategy_trader.add_trade(trade)

    results['messages'].append("Assigned trade %i on %s:%s" % (trade.id, strategy.identifier, strategy_trader.instrument.market_id))

    return results
