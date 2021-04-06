# @date 2020-01-23
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Strategy command trader modify quantity for any traders

from strategy.command.strategycmdstrategytradermodify import cmd_strategy_trader_modify


def cmd_strategy_trader_modify_all(strategy, data):
    """
    Modify any traders.
    """
    results = {
        'messages': [],
        'error': False
    }

    try:
        action = data.get('action')
    except Exception:
        results['error'] = True
        results['messages'].append("Invalid trader action")

    # @todo activity

    # if action == "enable":
    #         if not strategy_trader.activity:
    #             strategy_trader.set_activity(True)
    #             results['messages'].append("Enabled strategy trader for market %s" % strategy_trader.instrument.market_id)
    #         else:
    #             results['messages'].append("Already enabled strategy trader for market %s" % strategy_trader.instrument.market_id)

    #         results['activity'] = strategy_trader.activity

    # elif action == "disable":
    #     if strategy_trader.activity:
    #         strategy_trader.set_activity(False)
    #         results['messages'].append("Disabled strategy trader for market %s" % strategy_trader.instrument.market_id)
    #     else:
    #         results['messages'].append("Already disabled strategy trader for market %s" % strategy_trader.instrument.market_id)

    #     results['activity'] = strategy_trader.activity

    # elif action == "toggle":
    #     if strategy_trader.activity:
    #         strategy_trader.set_activity(False)
    #         results['messages'].append("Disabled strategy trader for market %s" % strategy_trader.instrument.market_id)
    #     else:
    #         strategy_trader.set_activity(True)
    #         results['messages'].append("Enabled strategy trader for market %s" % strategy_trader.instrument.market_id)

    #     results['activity'] = strategy_trader.activity

    #
    # affinity
    #

    if action == "set-affinity":
        affinity = 0

        # test values before to avoid multiple times the error
        try:
            affinity = int(data.get('affinity', 5))
        except Exception:
            results['error'] = True
            results['messages'].append("Invalid affinity")

        if not 0 <= affinity <= 10:
            results['error'] = True
            results['messages'].append("Affinity must be between 0 and 10 inclusive")

        if results['error']:
            return results

        results = []

        with strategy._mutex:
            for k, strategy_trader in strategy._strategy_traders.items():
                results.append(cmd_strategy_trader_modify(strategy, strategy_trader, data))

    #
    # quantity/size
    #

    if action == "set-quantity":
        # modify quantity/max-factor on any traders on the strategy
        quantity = 0.0
        max_factor = 1

        # test values before to avoid multiple times the error
        try:
            quantity = float(data.get('quantity', -1))
        except Exception:
            results['error'] = True
            results['messages'].append("Invalid quantity")

        try:
            max_factor = int(data.get('max-factor', 1))
        except Exception:
            results['error'] = True
            results['messages'].append("Invalid max factor")

        if quantity < 0.0:
            results['error'] = True
            results['messages'].append("Quantity must be greater than zero")

        if max_factor <= 0:
            results['error'] = True
            results['messages'].append("Max factor must be greater than zero")

        if results['error']:
            return results

        results = []

        with strategy._mutex:
            for k, strategy_trader in strategy._strategy_traders.items():
                results.append(cmd_strategy_trader_modify(strategy, strategy_trader, data))

    #
    # option
    #

    elif action == "set-option":
        option = data.get('option')
        value = data.get('value')

        if not option or type(option) is not str:
            results['error'] = True
            results['messages'].append("Option must be defined and valid")

        if value is None:
            results['error'] = True
            results['messages'].append("Value must be defined")

        if value is not None and type(value) not in (str, int, float):
            results['error'] = True
            results['messages'].append("Value must be a valid string, integer or decimal")

        if value is not None and type(value) is str and not value:
            results['error'] = True
            results['messages'].append("Value cannot be empty")

        if results['error']:
            return results

        results = []

        with strategy._mutex:
            for k, strategy_trader in strategy._strategy_traders.items():
                results.append(cmd_strategy_trader_modify(strategy, strategy_trader, data))

    return results
