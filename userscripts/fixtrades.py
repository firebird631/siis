import time

from common.signal import Signal

import logging

logger = logging.getLogger('siis.strategy')


def run_once(watcher_service, trader_service, strategy_service, monitor_service, notifier_service):
    results = {
        'messages': [],
        'error': False
    }

    trader = trader_service.trader()

    for market_id, strategy_trader in strategy_service.strategy()._strategy_traders.items():
        market = trader.market(market_id)

        with strategy_trader._mutex:
            with strategy_trader._trade_mutex:
                for trade in strategy_trader.trades:
                    delay = 0

                    if trade.entry_oid:
                        results['messages'].append("For trade entry %s %i" % (market_id, trade.id))
                        data = trader.order_info(trade.entry_oid, market)
                        delay += 1

                        if data is None:
                            # API error, do nothing need retry
                            results['messages'].append("Nothing for trade %s" % str(trade.entry_oid))
                        else:
                            if data['id'] is None:
                                # cannot retrieve the trade, wrong id
                                results['messages'].append("Wrong id %s" % str(trade.entry_oid))
                            else:
                                if data['cumulative-filled'] > trade.e or data['fully-filled']:
                                    trade.order_signal(Signal.SIGNAL_ORDER_TRADED, data, data['ref-id'], market)

                                if data['status'] in ('expired', 'canceled'):
                                    trade.order_signal(Signal.SIGNAL_ORDER_CANCELED, data['id'], data['ref-id'], market)

                                elif data['status'] in ('deleted', 'closed'):
                                    trade.order_signal(Signal.SIGNAL_ORDER_DELETED, data['id'], data['ref-id'], market)

                                # for k, v in data.items():
                                #     results['messages'].append("%s: %s" % (k, str(v)))

                    if trade.limit_oid:
                        results['messages'].append("For trade limit %s %i" % (market_id, trade.id))
                        data = trader.order_info(trade.limit_oid, market)
                        delay += 1

                        if data is None:
                            # API error, do nothing need retry
                            results['messages'].append("Nothing for trade %s" % str(trade.limit_oid))
                        else:
                            if data['id'] is None:
                                # cannot retrieve the trade, wrong id
                                results['messages'].append("Wrong id %s" % str(trade.limit_oid))
                            else:
                                if data['cumulative-filled'] > trade.x or data['fully-filled']:
                                    trade.order_signal(Signal.SIGNAL_ORDER_TRADED, data, data['ref-id'], market)

                                if data['status'] in ('expired', 'canceled'):
                                    trade.order_signal(Signal.SIGNAL_ORDER_CANCELED, data['id'], data['ref-id'], market)

                                elif data['status'] in ('deleted', 'closed'):
                                    trade.order_signal(Signal.SIGNAL_ORDER_DELETED, data['id'], data['ref-id'], market)

                                # for k, v in data.items():
                                #     results['messages'].append("%s: %s" % (k, str(v)))

                    if trade.stop_oid:
                        results['messages'].append("For trade stop %s %i" % (market_id, trade.id))
                        data = trader.order_info(trade.stop_oid, market)
                        delay += 1

                        if data is None:
                            # API error, do nothing need retry
                            results['messages'].append("Nothing for trade %s" % str(trade.stop_oid))
                        else:
                            if data['id'] is None:
                                # cannot retrieve the trade, wrong id
                                results['messages'].append("Wrong id %s" % str(trade.stop_oid))
                            else:
                                if data['cumulative-filled'] > trade.x or data['fully-filled']:
                                    trade.order_signal(Signal.SIGNAL_ORDER_TRADED, data, data['ref-id'], market)

                                if data['status'] in ('expired', 'canceled'):
                                    trade.order_signal(Signal.SIGNAL_ORDER_CANCELED, data['id'], data['ref-id'], market)

                                elif data['status'] in ('deleted', 'closed'):
                                    trade.order_signal(Signal.SIGNAL_ORDER_DELETED, data['id'], data['ref-id'], market)

                                # for k, v in data.items():
                                #     results['messages'].append("%s: %s" % (k, str(v)))

                    time.sleep(delay * 2)

    return results
