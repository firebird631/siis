# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trade clean

def cmd_trade_clean(strategy, strategy_trader, data):
    """
    Clean an existing trade according data on given strategy_trader.

    @note If trade-id is -1 assume the last trade.
    """
    results = {
        'messages': [],
        'error': False
    }

    # retrieve the trade
    trade_id = -1

    try:
        trade_id = int(data.get('trade-id'))
    except Exception:
        results['error'] = True
        results['messages'].append("Invalid trade identifier")

    if results['error']:
        return results

    trade = None
    trader = strategy.trader()

    with strategy_trader._mutex:
        if trade_id == -1 and strategy_trader.trades:
            trade = strategy_trader.trades[-1]
        else:
            for t in strategy_trader.trades:
                if t.id == trade_id:
                    trade = t
                    break

        if trade:
            # remove orders
            trade.remove(trader, strategy_trader.instrument)

            # and the trade, don't keet it for history because unqualifiable
            strategy_trader.remove_trade(trade)

            # update strategy-trader
            strategy.send_update_strategy_trader(strategy_trader.instrument.market_id)

            # add a success result message
            results['messages'].append("Force remove trade %i on %s:%s" % (trade.id, strategy.identifier, strategy_trader.instrument.market_id))
        else:
            results['error'] = True
            results['messages'].append("Invalid trade identifier %i" % trade_id)

    return results
