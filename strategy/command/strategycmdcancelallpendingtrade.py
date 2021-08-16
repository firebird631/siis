# @date 2021-08-10
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy command cancel all pending trade

from terminal.terminal import Terminal

from .strategycmdtradecancelpendingtrade import cmd_trade_cancel_pending


def cmd_strategy_cancel_all_pending_trade(strategy, data):
    # manually cancel any pending trades without realized quantity
    # if the trade is active it will not be canceled by cmd_trade_cancel_pending
    market_id = data.get('market-id')
    strategy_trader = None

    if market_id:
        strategy_trader = strategy._strategy_traders.get(market_id)

        if not strategy_trader:
            # lookup by symbol name
            instrument = strategy.find_instrument(market_id)
            market_id = instrument.market_id if instrument else None

            strategy_trader = strategy._strategy_traders.get(market_id)

    if strategy_trader and strategy_trader.has_trades():
        Terminal.inst().notice("Multi trade cancel for strategy %s - %s" % (strategy.name, strategy.identifier), view='content')

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

            result = cmd_trade_cancel_pending(strategy, strategy_trader, data, silent=True)

            if result:
                if result['error']:
                    Terminal.inst().info(result['messages'][0], view='status')
                else:
                    Terminal.inst().info("Done", view='status')

                for message in result['messages']:
                    Terminal.inst().message(message, view='content')

            results.append(result)

        # update strategy-trader, can be multiple trade but on the same strategy-trader
        if trades:
            strategy.send_update_strategy_trader(strategy_trader.instrument.market_id)

        return results
    else:
        Terminal.inst().notice("Multi trade cancel for strategy %s - %s" % (strategy.name, strategy.identifier), view='content')

        # retrieve any trades for any traders
        trades = []
        markets_ids = set()

        with strategy._mutex:
            for market_id, strategy_trader in strategy._strategy_traders.items():
                # if there is some trade, cancel or close them, else goes to the next trader
                if strategy_trader.has_trades():
                    trades.extend([(strategy_trader.instrument.market_id, trade_id) for trade_id in strategy_trader.list_trades()])
                    markets_ids.add(strategy_trader.instrument.market_id)

        # multi command
        results = []

        for trade in trades:
            # retrieve the trade and apply the modification
            strategy_trader = strategy._strategy_traders.get(trade[0])
            data['trade-id'] = trade[1]

            result = cmd_trade_cancel_pending(strategy, strategy_trader, data, silent=True)

            if result:
                if result['error']:
                    Terminal.inst().info(result['messages'][0], view='status')
                else:
                    Terminal.inst().info(" Done", view='status')

                for message in result['messages']:
                    Terminal.inst().message(message, view='content')

            results.append(result)

        if trades:
            for market_id in markets_ids:
                # update strategy-trader, can be multiple trades on different strategy-trader
                strategy.send_update_strategy_trader(market_id)

        return results
