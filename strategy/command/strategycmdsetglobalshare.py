# @date 2021-10-11
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy command set global share for any traders


def cmd_strategy_set_global_share(strategy, data):
    """
    Modify global share for any traders.
    """
    results = {
        'messages': [],
        'error': False
    }

    action = data.get('action')
    step = data.get('step', 0.0)
    context = data.get('context', None)

    ctx_cnt = 0

    def apply_to_context(local_context, status, step_value=0.0):
        if status:
            # on => global-share mode,
            local_context.modify_trade_quantity_type('global-share', step_value)
        else:
            # off => normal mode, instrument quantity
            local_context.modify_trade_quantity_type('normal', 0.0)

    if action == 'global-share':
        if step <= 0.0:
            # add an error result message
            results['error'] = True
            results['messages'].append("Step must be great than zero when setting global share for %s" %
                                       strategy.identifier)
        else:
            with strategy._mutex:
                for market_id, strategy_trader in strategy._strategy_traders.items():
                    if context:
                        # retrieve context
                        ctx = strategy_trader.retrieve_context(context)

                        if ctx is not None:
                            ctx_cnt += 1
                            apply_to_context(ctx, True, step)
                    else:
                        context_ids = strategy_trader.contexts_ids()

                        for context_id in context_ids:
                            # retrieve context
                            ctx = strategy_trader.retrieve_context(context_id)

                            if ctx is not None:
                                apply_to_context(ctx, True, step)

    elif action == 'normal':
        with strategy._mutex:
            for market_id, strategy_trader in strategy._strategy_traders.items():
                if context:
                    # retrieve context
                    ctx = strategy_trader.retrieve_context(context)

                    if ctx is not None:
                        ctx_cnt += 1
                        apply_to_context(ctx, False)
                else:
                    context_ids = strategy_trader.contexts_ids()

                    for context_id in context_ids:
                        # retrieve context
                        ctx = strategy_trader.retrieve_context(context_id)

                        if ctx is not None:
                            apply_to_context(ctx, False)
    else:
        # add an error result message
        results['error'] = True
        results['messages'].append("Invalid action for set global share for %s" % strategy.identifier)

    if context and not ctx_cnt:
        # add an error result message
        print("toto")
        results['error'] = True
        results['messages'].append("Unknown context %s when setting global share for %s" % (
            context, strategy.identifier))

    return results
