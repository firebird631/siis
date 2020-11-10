# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trade exit

def cmd_trade_exit(strategy, strategy_trader, data):
    """
    Exit an existing trade according data on given strategy_trader.

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
            price = strategy_trader.instrument.close_exec_price(trade.direction)

            if not trade.is_active():
                # cancel open
                trade.cancel_open(trader, strategy_trader.instrument)

                # add a success result message
                results['messages'].append("Cancel trade %i on %s:%s" % (trade.id, strategy.identifier, strategy_trader.instrument.market_id))
            else:
                # close or cancel
                trade.close(trader, strategy_trader.instrument)

                # add a success result message
                results['messages'].append("Close trade %i on %s:%s at market price %s" % (
                    trade.id, strategy.identifier, strategy_trader.instrument.market_id, strategy_trader.instrument.format_price(price)))
        else:
            results['error'] = True
            results['messages'].append("Invalid trade identifier %i" % trade_id)

    return results
