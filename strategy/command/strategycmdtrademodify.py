# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trade modify

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strategy.strategy import Strategy
    from strategy.strategytrader import StrategyTrader


def cmd_trade_modify(strategy: Strategy, strategy_trader: StrategyTrader, data: dict) -> dict:
    """
    Modify a trade according data on given strategy_trader.

    @note If trade-id is -1 assume the last trade.
    """
    results = {
        'messages': [],
        'error': False
    }

    # retrieve the trade
    trade_id = -1
    action = ""
    notify = False  # excepted for modify SL/TP because they are managed directly

    try:
        trade_id = int(data.get('trade-id'))
        action = data.get('action')
    except Exception:
        results['error'] = True
        results['messages'].append("Invalid trade identifier")

    if results['error']:
        return results

    trade = None

    with strategy_trader._mutex:
        if trade_id == -1 and strategy_trader.trades:
            trade = strategy_trader.trades[-1]
        else:
            for t in strategy_trader.trades:
                if t.id == trade_id:
                    trade = t
                    break

        if trade:
            # modify SL
            if action == 'stop-loss' and 'stop-loss' in data and type(data['stop-loss']) in (float, int):
                # method, default is a price
                method = data.get('method', "price")

                # @todo does take care of the trade direction in case of short to negate the value ? see for TP too
                if method not in ("price", "delta-percent", "delta-price", "entry-delta-percent", "entry-delta-price",
                                  "market-delta-percent", "market-delta-price"):

                    results['error'] = True
                    results['messages'].append("Stop-loss unsupported method for trade %i" % trade.id)

                    return results

                if method == "delta-percent" and data['stop-loss'] != 0.0:
                    stop_loss_price = trade.sl * (1.0 + data['stop-loss'])

                elif method == "delta-price" and data['stop-loss'] != 0.0:
                    stop_loss_price = trade.sl + data['stop-loss']

                elif method == "entry-delta-percent":
                    stop_loss_price = trade.aep * (1.0 + data['stop-loss'])

                elif method == "entry-delta-price":
                    stop_loss_price = trade.aep + data['stop-loss']

                elif method == "market-delta-percent" and data['stop-loss'] != 0.0:
                    stop_loss_price = strategy_trader.instrument.close_exec_price(
                        trade.direction) * (1.0 + data['stop-loss'])

                elif method == "market-delta-price" and data['stop-loss'] != 0.0:
                    stop_loss_price = strategy_trader.instrument.close_exec_price(
                        trade.direction) + data['stop-loss']

                elif method == "price" and data['stop-loss'] >= 0.0:
                    stop_loss_price = data['stop-loss']

                else:
                    results['error'] = True
                    results['messages'].append("Stop-loss invalid method or value for trade %i" % trade.id)

                    return results

                # apply
                if stop_loss_price < 0.0:
                    results['error'] = True
                    results['messages'].append("Stop-loss price is negative for trade %i" % trade.id)

                    return results
                else:
                    if stop_loss_price == 0.0:
                        results['messages'].append("Remove stop-loss for trade %i" % trade.id)

                    # if have a previous hard order it will update it, else it will create the order only if
                    # force is defined. It could eventually remove the take-profit order on spot market
                    strategy_trader.trade_modify_stop_loss(
                        trade, stop_loss_price, trade.has_stop_order() or data.get('force', False))

                    # update strategy-trader
                    strategy.send_update_strategy_trader(strategy_trader.instrument.market_id)

            # modify TP
            elif action == 'take-profit' and 'take-profit' in data and type(data['take-profit']) in (float, int):
                # method, default is a price
                method = data.get('method', "price")

                if method not in ("price", "delta-percent", "delta-price", "entry-delta-percent", "entry-delta-price",
                                  "market-delta-percent", "market-delta-price"):

                    results['error'] = True
                    results['messages'].append("Take-profit unsupported method for trade %i" % trade.id)

                    return results

                if method == "delta-percent" and data['take-profit'] != 0.0:
                    take_profit_price = trade.tp * (1.0 + data['take-profit'])

                elif method == "delta-price" and data['take-profit'] != 0.0:
                    take_profit_price = trade.tp + data['take-profit']

                elif method == "entry-delta-percent":
                    take_profit_price = trade.aep * (1.0 + data['take-profit'])

                elif method == "entry-delta-price":
                    take_profit_price = trade.aep + data['take-profit']

                elif method == "market-delta-percent" and data['take-profit'] != 0.0:
                    take_profit_price = strategy_trader.instrument.close_exec_price(
                        trade.direction) * (1.0 + data['take-profit'])

                elif method == "market-delta-price" and data['take-profit'] != 0.0:
                    take_profit_price = strategy_trader.instrument.close_exec_price(
                        trade.direction) + data['take-profit']

                elif method == "price" and data['take-profit'] >= 0.0:
                    take_profit_price = data['take-profit']

                else:
                    results['error'] = True
                    results['messages'].append("Take-profit invalid method or value for trade %i" % trade.id)

                    return results

                # apply
                if take_profit_price < 0.0:
                    results['error'] = True
                    results['messages'].append("Take-profit price is negative for trade %i" % trade.id)

                    return results
                else:
                    if take_profit_price == 0.0:
                        results['messages'].append("Remove take-profit for trade %i" % trade.id)

                    # if have a previous hard order it will update it, else it will create the order only if
                    # force is defined. It could eventually remove the stop order on spot market
                    strategy_trader.trade_modify_take_profit(
                        trade, take_profit_price, trade.has_limit_order() or data.get('force', False))

                    # update strategy-trader
                    strategy.send_update_strategy_trader(strategy_trader.instrument.market_id)

            # add operation
            elif action == 'add-op':
                op_name = data.get('operation', "")

                if op_name in strategy.service.tradeops:
                    try:
                        # instantiate the operation
                        operation = strategy.service.tradeops[op_name]()

                        # and define the parameters
                        operation.init(data)

                        if operation.check(trade):
                            # append the operation to the trade
                            trade.add_operation(operation)
                            notify = True
                        else:
                            results['error'] = True
                            results['messages'].append("Operation checking error %s on trade %i" % (op_name, trade.id))

                    except Exception as e:
                        results['error'] = True
                        results['messages'].append(repr(e))
                else:
                    results['error'] = True
                    results['messages'].append("Unsupported operation %s on trade %i" % (op_name, trade.id))

            # remove operation
            elif action == 'del-op':
                trade_operation_id = -1

                if 'operation-id' in data and type(data.get('operation-id')) is int:
                    trade_operation_id = data['operation-id']

                if trade_operation_id > 0 and trade.remove_operation(trade_operation_id):
                    notify = True
                else:
                    results['error'] = True
                    results['messages'].append("Unknown operation-id on trade %i" % trade.id)

            # comment/uncomment a trade
            elif action == 'comment':
                comment = data.get('comment', "")

                if type(comment) is str:
                    if len(comment) <= 100:
                        trade.comment = comment
                        notify = True
                    else:
                        results['error'] = True
                        results['messages'].append("Comment string is 100 characters max, for trade %i" % trade.id)
                else:
                    results['error'] = True
                    results['messages'].append("Comment must be a string, for trade %i" % trade.id)

            else:
                # unsupported action
                results['error'] = True
                results['messages'].append("Unsupported action on trade %i" % trade.id)

        else:
            results['error'] = True
            results['messages'].append("Invalid trade identifier %i" % trade_id)

    if notify:
        strategy_trader.notify_trade_update(strategy.timestamp, trade)

    return results
