# @date 2021-08-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy command trader check and repair

def cmd_trade_check(strategy, strategy_trader, data):
    """
    Check and optional repair an existing trade according data on given strategy_trader.

    @note If trade-id is -1 assume the last trade.
    """
    results = {
        'messages': [],
        'error': False
    }

    # retrieve the trade
    trade_id = -1

    repair = data.get('repair', False)

    try:
        trade_id = int(data.get('trade-id'))
    except ValueError:
        results['error'] = True
        results['messages'].append("Invalid trade identifier")

    if results['error']:
        return results

    trade = None
    trader = strategy.trader()

    with strategy_trader._mutex:
        for t in strategy_trader.trades:
            if t.id == trade_id:
                trade = t
                break

        if trade:
            # check trade
            result = trade.check(trader, strategy_trader.instrument)

            if result >= 0:
                # add a success result message
                results['messages'].append("Checked trade %i on %s:%s" % (
                    trade.id, strategy.identifier, strategy_trader.instrument.market_id))

                if result == 0 and repair:
                    if trade.repair(trader, strategy_trader.instrument):
                        # add a success result message
                        results['messages'].append("Repaired trade %i on %s:%s" % (
                            trade.id, strategy.identifier, strategy_trader.instrument.market_id))
                    else:
                        results['error'] = True
                        results['messages'].append("Unable to repair trade %i on %s:%s" % (
                            trade.id, strategy.identifier, strategy_trader.instrument.market_id))

                # update strategy-trader
                strategy.send_update_strategy_trader(strategy_trader.instrument.market_id)
            else:
                # add an error result message
                results['error'] = True
                results['messages'].append("Unable to check trade %i on %s:%s" % (
                    trade.id, strategy.identifier, strategy_trader.instrument.market_id))
        else:
            results['error'] = True
            results['messages'].append("Invalid trade identifier %i" % trade_id)

    return results
