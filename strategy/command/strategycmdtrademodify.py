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
                if data['stop-loss'] > 0.0:
                    if trade.has_stop_order() or data.get('force', False):
                        trade.modify_stop_loss(strategy.trader(), strategy_trader.instrument, data['stop-loss'])
                    else:
                        trade.sl = data['stop-loss']

                    # update strategy-trader
                    strategy.send_update_strategy_trader(strategy_trader.instrument.market_id)
                else:
                    results['error'] = True
                    results['messages'].append("Take-profit must be greater than 0 on trade %i" % trade.id)

            # modify TP
            elif action == 'take-profit' and 'take-profit' in data and type(data['take-profit']) in (float, int):
                if data['take-profit'] > 0.0:
                    if trade.has_limit_order() or data.get('force', False):
                        trade.modify_take_profit(strategy.trader(), strategy_trader.instrument, data['take-profit'])
                    else:
                        trade.tp = data['take-profit']

                    # update strategy-trader
                    strategy.send_update_strategy_trader(strategy_trader.instrument.market_id)
                else:
                    results['error'] = True
                    results['messages'].append("Take-profit must be greater than 0 on trade %i" % trade.id)

            # add operation
            elif action == 'add-op':
                op_name = data.get('operation', "")

                if op_name in strategy.service.tradeops:
                    try:
                        # instanciate the operation
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
