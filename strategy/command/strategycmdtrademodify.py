# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trade modify

def cmd_trade_modify(strategy, strategy_trader, data):
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

                    if trade.has_stop_order() or data.get('force', False):
                        trade.modify_stop_loss(strategy.trader(), strategy_trader.instrument, stop_loss_price)
                    else:
                        trade.sl = stop_loss_price

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

                    if trade.has_limit_order() or data.get('force', False):
                        trade.modify_take_profit(strategy.trader(), strategy_trader.instrument, take_profit_price)
                    else:
                        trade.tp = take_profit_price

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

                if not trade.remove_operation(trade_operation_id):
                    results['error'] = True
                    results['messages'].append("Unknown operation-id on trade %i" % trade.id)
            else:
                # unsupported action
                results['error'] = True
                results['messages'].append("Unsupported action on trade %i" % trade.id)

        else:
            results['error'] = True
            results['messages'].append("Invalid trade identifier %i" % trade_id)

    return results
