# @date 2024-07-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2024 Dream Overflow
# Strategy command enable/disable daily limit for any traders

from strategy.handler.dailylimithandler import DailyLimitHandler


def cmd_strategy_daily_limit(strategy, data):
    """
    Modify global share for any traders.
    """
    results = {
        'messages': [],
        'error': False
    }

    action = data.get('action')

    profit_limit_pct = data.get('profit-limit-pct', 0.0)
    profit_limit_currency = data.get('profit-limit-currency', 0.0)

    loss_limit_pct = data.get('loss-limit-pct', 0.0)
    loss_limit_currency = data.get('loss-limit-currency', 0.0)

    if action == 'daily-limit':
        if profit_limit_pct <= 0.0 and profit_limit_currency <= 0.0:
            results['error'] = True
            results['messages'].append("Profit must be a positive value in percent or account currency")
            return results

        if loss_limit_pct <= 0.0 and loss_limit_currency <= 0.0:
            results['error'] = True
            results['messages'].append("Loss must be a positive value in percent or account currency")
            return results

        handler = DailyLimitHandler(strategy.trader(),
                                    profit_limit_pct, profit_limit_currency,
                                    loss_limit_pct, loss_limit_currency)

        with strategy.mutex:
            for market_id, strategy_trader in strategy._strategy_traders.items():
                strategy_trader.install_handler(handler)

    elif action == 'normal':
        with strategy.mutex:
            for market_id, strategy_trader in strategy._strategy_traders.items():
                strategy_trader.uninstall_handler("", DailyLimitHandler.name)
    else:
        # add an error result message
        results['error'] = True
        results['messages'].append("Invalid action for set global share for %s" % strategy.identifier)

    return results
