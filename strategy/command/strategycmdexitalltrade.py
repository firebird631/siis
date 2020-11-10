# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command exit all trade

from terminal.terminal import Terminal

from .strategycmdtradeexit import cmd_trade_exit

def cmd_strategy_exit_all_trade(strategy, data):
    # manually trade modify a trade or any trades (add/remove an operation)
    market_id = data.get('market-id')

    strategy_trader = strategy._strategy_traders.get(market_id)
    if strategy_trader and strategy_trader.has_trades():
        Terminal.inst().notice("Multi trade exit for strategy %s - %s" % (strategy.name, strategy.identifier), view='content')

        # retrieve any trades
        trades = []

        # if there is some trade, cancel or close them, else goes to the next trader
        if strategy_trader.has_trades():
            trades.extend([(strategy_trader.instrument.market_id, trade_id) for trade_id in strategy_trader.list_trades()])

        # multi command
        results = []

        for trade in trades:
            # retrieve the trade and apply the modification
            strategy_trader = strategy._strategy_traders.get(trade[0])
            data['trade-id'] = trade[1]

            result = cmd_trade_exit(strategy, strategy_trader, data)

            if result:
                if result['error']:
                    Terminal.inst().info(result['messages'][0], view='status')
                else:
                    Terminal.inst().info("Done", view='status')

                for message in result['messages']:
                    Terminal.inst().message(message, view='content')

            results.append(result)

        return results
    else:
        Terminal.inst().notice("Multi trade exit for strategy %s - %s" % (strategy.name, strategy.identifier), view='content')

        # retrieve any trades for any traders
        trades = []

        with strategy._mutex:
            for market_id, strategy_trader in strategy._strategy_traders.items():
                # if there is some trade, cancel or close them, else goes to the next trader
                if strategy_trader.has_trades():
                    trades.extend([(strategy_trader.instrument.market_id, trade_id) for trade_id in strategy_trader.list_trades()])

        # multi command
        results = []

        for trade in trades:
            # retrieve the trade and apply the modification
            strategy_trader = strategy._strategy_traders.get(trade[0])
            data['trade-id'] = trade[1]

            result = cmd_trade_exit(strategy, strategy_trader, data)

            if result:
                if result['error']:
                    Terminal.inst().info(result['messages'][0], view='status')
                else:
                    Terminal.inst().info("Done", view='status')

                for message in result['messages']:
                    Terminal.inst().message(message, view='content')

            results.append(result)

        return results
