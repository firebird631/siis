def run_once(watcher_service, trader_service, strategy_service, monitor_service, notifier_service):
    results = {
        'messages': [],
        'error': False
    }

    market_id = 'AAVEEUR'

    trader = trader_service.trader()
    market = trader.market(market_id)

    with trader._mutex:
        for oid, order in trader._orders.items():
            if order.symbol == market_id:
                data = trader.order_info(order.order_id, market)

                if data is None:
                    # API error, do nothing need retry
                    results['messages'].append("Nothing for order %s" % str(order.order_id))
                else:
                    if data['id'] is None:
                        # cannot retrieve the order, wrong id
                        results['messages'].append("Wrong id %s" % str(order.order_id))
                    else:
                        for k, v in data.items():
                            results['messages'].append("%s: %s" % (k, str(v)))

    return results
