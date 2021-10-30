# @date 2021-08-10
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy command trade cancel if pending and without quantity

def cmd_trade_cancel_pending(strategy, strategy_trader, data, silent=False):
    """
    Cancel an existing trade according data on given strategy_trader.
    If the trade is active it will not be canceled.
    An error message is returned if the trade cannot be canceled, except if silent is defined.
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
        # retrieve the trade
        with strategy_trader._trade_mutex:
            for t in strategy_trader.trades:
                if t.id == trade_id:
                    trade = t
                    break

        if trade:
            if not trade.is_active():
                # cancel open
                if trade.cancel_open(trader, strategy_trader.instrument) > 0:
                    # add a success result message
                    results['messages'].append("Cancel trade %i on %s:%s" % (
                        trade.id, strategy.identifier, strategy_trader.instrument.market_id))

                    # update strategy-trader
                    strategy.send_update_strategy_trader(strategy_trader.instrument.market_id)
                else:
                    results['error'] = True
                    results['messages'].append("Error during cancel trade %i on %s:%s" % (
                        trade.id, strategy.identifier, strategy_trader.instrument.market_id))
            else:
                # cannot cancel if active, add a reject result message
                if not silent:
                    results['messages'].append("Cannot cancel active trade %i on %s:%s" % (
                        trade.id, strategy.identifier, strategy_trader.instrument.market_id))
        else:
            results['error'] = True
            results['messages'].append("Invalid trade identifier %i" % trade_id)

    return results
