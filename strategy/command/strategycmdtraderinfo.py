# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trader info

from terminal.terminal import Terminal

def cmd_trader_info(strategy, data):
    # info on the strategy
    if 'market-id' in data:
        market_id = data['market-id']

        with strategy._mutex:
            strategy_trader = strategy._strategy_traders.get(market_id)

            if not strategy_trader:
                # lookup by symbol name
                instrument = strategy.find_instrument(market_id)
                market_id = instrument.market_id if instrument else None

                strategy_trader = strategy._strategy_traders.get(market_id)

            if strategy_trader:
                Terminal.inst().message("Market %s of strategy %s identified by \\2%s\\0 is %s. Trade quantity is %s x%s" % (
                    data['market-id'], strategy.name, strategy.identifier, "active" if strategy_trader.activity else "paused",
                        strategy_trader.instrument.trade_quantity, strategy_trader.instrument.trade_max_factor),
                        view='content')
    else:
        Terminal.inst().message("Strategy %s is identified by \\2%s\\0" % (strategy.name, strategy.identifier), view='content')

        enabled = []
        disabled = []

        with strategy._mutex:
            for k, strategy_trader in strategy._strategy_traders.items():
                if strategy_trader.activity:
                    enabled.append(k)
                else:
                    disabled.append(k)

        if enabled:
            enabled = [e if i%10 else e+'\n' for i, e in enumerate(enabled)]
            Terminal.inst().message("Enabled instruments (%i): %s" % (len(enabled), " ".join(enabled)), view='content')

        if disabled:
            disabled = [e if i%10 else e+'\n' for i, e in enumerate(disabled)]
            Terminal.inst().message("Disabled instruments (%i): %s" % (len(disabled), " ".join(disabled)), view='content')
