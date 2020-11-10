# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trader modify

def cmd_strategy_trader_modify(strategy, strategy_trade, data):
    """
    Modify a strategy-trader state, a region or an alert.
    """        
    results = {
        'messages': [],
        'error': False
    }

    action = ""
    expiry = 0
    countdown = -1
    timeframe = 0

    with strategy_trader._mutex:
        try:
            action = data.get('action')
        except Exception:
            results['error'] = True
            results['messages'].append("Invalid trader action")

        if action == "add-region":
            region_name = data.get('region', "")

            try:
                stage = int(data.get('stage', 0))
                direction = int(data.get('direction', 0))
                created = float(data.get('created', 0.0))
                expiry = float(data.get('expiry', 0.0))

                if 'timeframe' in data and type(data['timeframe']) is str:
                    timeframe = timeframe_from_str(data['timeframe'])

            except ValueError:
                results['error'] = True
                results['messages'].append("Invalid parameters")

            if not results['error']:
                if region_name in strategy.service.regions:
                    try:
                        # instanciate the region
                        region = strategy.service.regions[region_name](created, stage, direction, timeframe)

                        if expiry:
                            region.set_expiry(expiry)

                        # and defined the parameters
                        region.init(data)

                        if region.check():
                            # append the region to the strategy trader
                            strategy_trader.add_region(region)
                        else:
                            results['error'] = True
                            results['messages'].append("Region checking error %s" % (region_name,))

                    except Exception as e:
                        results['error'] = True
                        results['messages'].append(repr(e))
                else:
                    results['error'] = True
                    results['messages'].append("Unsupported region %s" % (region_name,))

        elif action == "del-region":
            try:
                region_id = int(data.get('region-id', -1))
            except Exception:
                results['error'] = True
                results['messages'].append("Invalid region identifier format")

            if region_id >= 0:
                if not strategy_trader.remove_region(region_id):
                    results['messages'].append("Invalid region identifier")

        elif action == 'add-alert':
            alert_name = data.get('alert', "")

            try:
                created = float(data.get('created', 0.0))
                expiry = float(data.get('expiry', 0.0))
                countdown = int(data.get('countdown', -1))
                timeframe = 0

                if 'timeframe' in data:
                    if type(data['timeframe']) is str:
                        timeframe = timeframe_from_str(data['timeframe'])
                    elif type(data['timeframe']) in (float, int):
                        timeframe = data['timeframe']

            except ValueError:
                results['error'] = True
                results['messages'].append("Invalid parameters")

            if not results['error']:
                if alert_name in strategy.service.alerts:
                    try:
                        # instanciate the alert
                        alert = strategy.service.alerts[alert_name](created, timeframe)
                        alert.set_countdown(countdown)

                        if expiry:
                            alert.set_expiry(expiry)                         

                        # and defined the parameters
                        alert.init(data)

                        if alert.check():
                            # append the alert to the strategy trader
                            strategy_trader.add_alert(alert)
                        else:
                            results['error'] = True
                            results['messages'].append("Alert checking error %s" % (alert_name,))

                    except Exception as e:
                        results['error'] = True
                        results['messages'].append(repr(e))
                else:
                    results['error'] = True
                    results['messages'].append("Unsupported alert %s" % (alert_name,))

        elif action == 'del-alert':
            try:
                alert_id = int(data.get('alert-id', -1))
            except Exception:
                results['error'] = True
                results['messages'].append("Invalid alert identifier format")

            if alert_id >= 0:
                if not strategy_trader.remove_alert(alert_id):
                    results['messages'].append("Invalid alert identifier")

        elif action == "enable":
            if not strategy_trader.activity:
                strategy_trader.set_activity(True)
                results['messages'].append("Enabled strategy trader for market %s" % strategy_trader.instrument.market_id)
            else:
                results['messages'].append("Already enabled strategy trader for market %s" % strategy_trader.instrument.market_id)

        elif action == "disable":
            if strategy_trader.activity:
                strategy_trader.set_activity(False)
                results['messages'].append("Disabled strategy trader for market %s" % strategy_trader.instrument.market_id)
            else:
                results['messages'].append("Already disabled strategy trader for market %s" % strategy_trader.instrument.market_id)

        elif action == "set-quantity":
            quantity = 0.0
            max_factor = 1

            try:
                quantity = float(data.get('quantity', -1))
            except Exception:
                results['error'] = True
                results['messages'].append("Invalid quantity")

            try:
                max_factor = int(data.get('max-factor', 1))
            except Exception:
                results['error'] = True
                results['messages'].append("Invalid max factor")

            if quantity < 0.0:
                results['error'] = True
                results['messages'].append("Quantity must be greater than zero")

            if max_factor <= 0:
                results['error'] = True
                results['messages'].append("Max factor must be greater than zero")

            if quantity > 0.0 and strategy_trader.instrument.trade_quantity != quantity:
                strategy_trader.instrument.trade_quantity = quantity
                results['messages'].append("Modified trade quantity for %s to %s" % (strategy_trader.instrument.market_id, quantity))

            if max_factor > 0 and strategy_trader.instrument.trade_max_factor != max_factor:
                strategy_trader.instrument.trade_max_factor = max_factor
                results['messages'].append("Modified trade quantity max factor for %s to %s" % (strategy_trader.instrument.market_id, max_factor))

        else:
            results['error'] = True
            results['messages'].append("Invalid action")

    return results