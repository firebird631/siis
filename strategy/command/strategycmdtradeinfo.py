# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trade info

def cmd_trade_info(strategy, strategy_trader, data):
    """
    Get trade info according data on given strategy_trader.

    @note If trade-id is -1 assume the last trade.
    """        
    results = {
        'messages': [],
        'error': False
    }

    trade_id = -1

    try:
        trade_id = int(data.get('trade-id'))
    except Exception:
        results['error'] = True
        results['messages'].append("Invalid trade identifier")

    if results['error']:
        return results

    trade = None

    with strategy_trader._mutex:
        if trade_id == -1 and strategy_trader.trades:
            trade = strategy_trader.trades[-1]
        else:
            for t in strategy_trader.trades:
                if t.id == trade_id:
                    trade = t
                    break

        if trade:
            # common
            results['messages'].append("Trade %i on %s :" % (trade.id, strategy_trader.instrument.symbol))

            # details
            results['messages'] += trade.info_report(strategy_trader)

            # operations
            results['messages'].append("Has %i operations:" % (len(trade.operations),))

            # @todo could be returned as a table
            for operation in trade.operations:
                results['messages'].append(" - #%i: %s" % (operation.id, operation.str_info()))
        else:
            results['error'] = True
            results['messages'].append("Invalid trade identifier %i" % trade_id)

    return results
