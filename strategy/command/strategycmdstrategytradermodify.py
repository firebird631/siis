# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trader modify

from common.utils import timeframe_from_str


def cmd_strategy_trader_modify(strategy, strategy_trader, data):
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

        #
        # regions
        #

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
                        # instantiate the region
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

        #
        # alerts
        #

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

            if data.get('price') is not None:
                # method, default is a price
                method = data.get('method', "price")
                price_source = data.get('price-src', 'bid')
                alert_price = 0.0

                if method not in ("price", "market-delta-percent", "market-delta-price"):
                    results['error'] = True
                    results['messages'].append("Alert unsupported price method %s" % method)

                if price_source == "bid":
                    market_price = strategy_trader.instrument.market_bid
                elif price_source == "ask":
                    market_price = strategy_trader.instrument.market_ask
                elif price_source == "mid":
                    market_price = strategy_trader.instrument.market_price
                else:
                    market_price = strategy_trader.instrument.market_price

                if method == "market-delta-percent" and data['price'] != 0.0:
                    alert_price = market_price * (1.0 + data['price'])
                elif method == "market-delta-price" and data['price'] != 0.0:
                    alert_price = market_price + data['price']
                elif method == "price" and data['price'] >= 0.0:
                    alert_price = data['price']
                else:
                    results['error'] = True
                    results['messages'].append("Alert invalid price method or value")

                # apply
                if alert_price < 0.0:
                    results['error'] = True
                    results['messages'].append("Alert price is negative")
                else:
                    # update with computed price
                    data['price'] = alert_price

            if not results['error']:
                if alert_name in strategy.service.alerts:
                    try:
                        # instantiate the alert
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

        #
        # activity
        #

        elif action == "enable":
            if not strategy_trader.activity:
                strategy_trader.set_activity(True)
                results['messages'].append("Enabled strategy trader for market %s" % strategy_trader.instrument.market_id)
            else:
                results['messages'].append("Already enabled strategy trader for market %s" % strategy_trader.instrument.market_id)

            results['activity'] = strategy_trader.activity

        elif action == "disable":
            if strategy_trader.activity:
                strategy_trader.set_activity(False)
                results['messages'].append("Disabled strategy trader for market %s" % strategy_trader.instrument.market_id)
            else:
                results['messages'].append("Already disabled strategy trader for market %s" % strategy_trader.instrument.market_id)

            results['activity'] = strategy_trader.activity

        elif action == "toggle":
            if strategy_trader.activity:
                strategy_trader.set_activity(False)
                results['messages'].append("Disabled strategy trader for market %s" % strategy_trader.instrument.market_id)
            else:
                strategy_trader.set_activity(True)
                results['messages'].append("Enabled strategy trader for market %s" % strategy_trader.instrument.market_id)

            results['activity'] = strategy_trader.activity

        #
        # quantity/size
        #

        elif action == "set-quantity":
            quantity = 0.0

            try:
                quantity = float(data.get('quantity', -1))
            except Exception:
                results['error'] = True
                results['messages'].append("Invalid quantity")

            if quantity < 0.0:
                results['error'] = True
                results['messages'].append("Quantity must be greater than zero")

            if results['error']:
                return results

            if 0.0 < quantity != strategy_trader.instrument.trade_quantity:
                strategy_trader.instrument.trade_quantity = quantity
                results['messages'].append("Modified trade quantity for %s to %s" % (
                    strategy_trader.instrument.market_id, quantity))

            results['quantity'] = strategy_trader.instrument.trade_quantity

        #
        # affinity
        #

        elif action == "set-affinity":
            affinity = 0

            try:
                affinity = int(data.get('affinity', 5))
            except Exception:
                results['error'] = True
                results['messages'].append("Invalid affinity")

            if not 0 <= affinity <= 100:
                results['error'] = True
                results['messages'].append("Affinity must be between 0 and 100 inclusive")

            if results['error']:
                return results

            if strategy_trader.affinity != affinity:
                strategy_trader.affinity = affinity
                results['messages'].append("Modified strategy trader affinity for %s to %s" % (
                    strategy_trader.instrument.market_id, affinity))

            results['affinity'] = strategy_trader.affinity

        elif action == "set-option":
            option = data.get('option')
            value = data.get('value')

            if not option or type(option) is not str:
                results['error'] = True
                results['messages'].append("Option must be defined and valid")

            if value is None:
                results['error'] = True
                results['messages'].append("Value must be defined")

            if value is not None and type(value) not in (str, int, float):
                results['error'] = True
                results['messages'].append("Value must be a valid string, integer or decimal")

            if value is not None and type(value) is str and not value:
                results['error'] = True
                results['messages'].append("Value cannot be empty")

            if results['error']:
                return results

            error = strategy_trader.check_option(option, value)

            if error:
                results['error'] = True
                results['messages'].append(error)

                return results

            strategy_trader.set_option(option, value)
            results['messages'].append("Modified strategy trader option %s for %s to %s" % (
                option, strategy_trader.instrument.market_id, value))

        else:
            results['error'] = True
            results['messages'].append("Invalid action")

    return results
