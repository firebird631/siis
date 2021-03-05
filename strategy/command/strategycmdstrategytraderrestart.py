# @date 2021-03-04
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy command trader restart

def cmd_strategy_trader_restart(strategy, strategy_trader, data):
    """
    Query strategy-trader restart a specific trader
    """        
    results = {
        'messages': [],
        'error': False
    }

    strategy_trader.restart()
    strategy.send_initialize_strategy_trader(strategy_trader.instrument.market_id)

    return results
