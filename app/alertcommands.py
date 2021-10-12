# @date 2020-03-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# terminal alert commands and registration

import time

from datetime import datetime

from terminal.command import Command
from strategy.strategy import Strategy
from trader.trader import Trader

from common.utils import timeframe_from_str
from instrument.instrument import Instrument
from strategy.alert.alert import Alert


class PriceCrossAlertCommand(Command):

    SUMMARY = "to manually add a price-cross alert on a strategy"
    HELP = (":price-cross-alert <market-id> <price>",
            "optional parameters:",
            "- C@<price> : cancelation price",
            "- @<timestamp|duration> : expiry",
            "- '<timeframe> : timeframe")
    
    def __init__(self, strategy_service):
        super().__init__('price-cross-alert', 'pca')

        self._strategy_service = strategy_service

    def parse_datetime(self, formatted):
        if formatted:
            try:
                result = None
                use_utc = False

                if formatted.endswith('Z'):
                    formatted = formatted.rstrip('Z')
                    use_utc = True

                if 'T' in formatted:
                    if formatted.count(':') == 2:
                        if formatted.count('.') == 1:
                            result = datetime.strptime(formatted, '%Y-%m-%dT%H:%M:%S.%f')
                        else:
                            result = datetime.strptime(formatted, '%Y-%m-%dT%H:%M:%S')
                    elif formatted.count(':') == 1:
                        result = datetime.strptime(formatted, '%Y-%m-%dT%H:%M')
                    elif formatted.count(':') == 0:
                        result = datetime.strptime(formatted, '%Y-%m-%dT%H')
                else:
                    if formatted.count('-') == 2:
                        result = datetime.strptime(formatted, '%Y-%m-%d')
                    elif formatted.count('-') == 1:
                        result = datetime.strptime(formatted, '%Y-%m')
                    elif formatted.count('-') == 0:
                        result = datetime.strptime(formatted, '%Y')

                if result:
                    if use_utc:
                        result = result.replace(tzinfo=UTC())

                    return result
            except:
                return None

        return None

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        market_id = None
        timeframe = -1

        action = "add-alert"
        alert = "price-cross"
        direction = 0
        expiry = 0.0
        created = self._strategy_service.timestamp
        countdown = -1

        price = 0.0
        cancelation = 0.0
        price_src = Alert.PRICE_SRC_BID

        # ie ":PCA EURUSD bid >1.12"
        if len(args) < 2:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            for value in args[1:]:
                if value.startswith('>'):
                    direction = 1
                    price = float(value[1:])
                elif value.startswith('<'):
                    direction = -1
                    price = float(value[1:])
                elif value == "bid":
                    price_src = Alert.PRICE_SRC_BID
                elif value == "ask":
                    price_src = Alert.PRICE_SRC_ASK
                elif value == "ofr":
                    price_src = Alert.PRICE_SRC_ASK
                elif value == "mid":
                    price_src = Alert.PRICE_SRC_MID
                elif value.startswith("x"):
                    countdown = int(value[1:])
                elif value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])
                elif value.startswith('C@'):
                    cancelation = float(value[2:])
                elif value.startswith('@'):
                    # expiry
                    if 'T' in value:
                        # parse a local or UTC datetime
                        expiry = self.parse_datetime(value[1:]).timestamp()
                    else:
                        # parse a duration in seconds, relative to now
                        duration = timeframe_from_str(value[1:])
                        expiry = created + duration

        except Exception:
            return False, "Invalid parameters"

        results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'market-id': market_id,
            'action': action,
            'alert': alert,
            'created': created,
            'timeframe': timeframe,
            'expiry': expiry,
            'countdown': countdown,
            'price': price,
            'direction': direction,
            'price-src': price_src,
            'cancelation': cancelation
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class RemoveAlertCommand(Command):

    SUMMARY = "to manually remove an alert from a strategy"

    def __init__(self, strategy_service):
        super().__init__('rmalert', 'DA')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        market_id = None

        action = 'del-alert'
        alert_id = None        

        # ie ":rmalert EURUSD 1"
        if len(args) < 2:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            alert_id = int(args[1])   
        except Exception:
            return False, "Invalid parameters"

        results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'market-id': market_id,
            'action': action,
            'alert-id': alert_id
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class AlertInfoCommand(Command):

    SUMMARY = "to get alert info for a specific strategy"

    def __init__(self, strategy_service):
        super().__init__('alert', 'A')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        market_id = None
        alert_id = None

        if len(args) >= 1:
            try:
                market_id = args[0]

                if len(args) >= 2:
                    alert_id = int(args[1])
                else:
                    alert_id = -1

            except Exception:
                return False, "Invalid parameters"

            results = self._strategy_service.command(Strategy.COMMAND_TRADER_INFO, {
                'market-id': market_id,
                'detail': 'alert',
                'alert-id': alert_id
            })

            return self.manage_results(results)
        else:
            return False, "Missing or invalid parameters"

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


def register_alert_commands(commands_handler, strategy_service):
    cmd = PriceCrossAlertCommand(strategy_service)
    commands_handler.register(cmd)

    cmd = RemoveAlertCommand(strategy_service)
    commands_handler.register(cmd)

    cmd = AlertInfoCommand(strategy_service)
    commands_handler.register(cmd)
