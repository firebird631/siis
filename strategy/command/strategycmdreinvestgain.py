# @date 2021-10-11
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy command enable/disable reinvest gain for any traders

from strategy.handler.reinvestgainhandler import ReinvestGainHandler


def cmd_strategy_reinvest_gain(strategy, data):
    """
    Modify global share for any traders.
    """
    results = {
        'messages': [],
        'error': False
    }

    action = data.get('action')
    trade_quantity = data.get('trade-quantity', 0.0)
    step = data.get('step', 0.0)
    context_id = data.get('context')
    initial_total_qty = data.get('initial-total-qty')

    if not context_id:
        results['error'] = True
        results['messages'].append("Context identifier must be specified for %s" % strategy.identifier)

        return results

    ctx_cnt = 0

    if action == 'reinvest-gain':
        if not step or step <= 0.0:
            # add an error result message
            results['error'] = True
            results['messages'].append("Step must be great than zero when setting global share for %s" %
                                       strategy.identifier)

            return results

        if not trade_quantity or trade_quantity <= 0.0:
            # add an error result message
            results['error'] = True
            results['messages'].append("Trade quantity must be great than zero when setting global share for %s" %
                                       strategy.identifier)

            return results

        handler = ReinvestGainHandler(context_id, trade_quantity, step)

        with strategy._mutex:
            for market_id, strategy_trader in strategy._strategy_traders.items():
                # retrieve context
                ctx = strategy_trader.retrieve_context(context_id)

                if ctx is not None:
                    ctx_cnt += 1
                    strategy_trader.install_handler(handler)

            # force the value of initial total quantity, only if acceptable
            if initial_total_qty is not None and initial_total_qty > handler.total_quantity:
                if initial_total_qty - handler.total_quantity < handler.trade_quantity:
                    handler._total_quantity = initial_total_qty

    elif action == 'normal':
        with strategy._mutex:
            for market_id, strategy_trader in strategy._strategy_traders.items():
                # retrieve context
                ctx = strategy_trader.retrieve_context(context_id)

                if ctx is not None:
                    ctx_cnt += 1
                    strategy_trader.uninstall_handler(context_id, ReinvestGainHandler.name)
    else:
        # add an error result message
        results['error'] = True
        results['messages'].append("Invalid action for set global share for %s" % strategy.identifier)

    if not ctx_cnt:
        # add an error result message
        results['error'] = True
        results['messages'].append("Unknown context %s when setting global share for %s" % (
            context_id, strategy.identifier))

    return results
