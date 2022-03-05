# @date 2020-03-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# terminal alert commands and registration

from terminal.command import Command
from strategy.strategy import Strategy

from common.utils import timeframe_from_str, UTC, parse_datetime
from strategy.alert.alert import Alert


class PriceCrossAlertCommand(Command):

    SUMMARY = "to manually add a price-cross alert on a strategy"
    HELP = (":price-cross-alert <market-id> <price>",
            "optional parameters:",
            "- C@<price> : cancellation price",
            "- @<timestamp|duration> : expiry",
            "- '<timeframe> : timeframe")
    
    def __init__(self, strategy_service):
        super().__init__('price-cross-alert', 'pca')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        timeframe = 0

        action = "add-alert"
        alert = "price-cross"
        direction = 0
        expiry = 0.0
        created = self._strategy_service.timestamp
        countdown = -1

        price = 0.0
        method = "price"  # or market-delta-percent or market-delta-price
        cancellation = 0.0
        price_src = Alert.PRICE_SRC_BID

        # ie ":PCA EURUSD bid >1.12 x1"
        if len(args) < 2:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            for value in args[1:]:
                if value.startswith('>'):
                    direction = 1

                    if value.endswith('%'):
                        if len(value) < 3:
                            return False, "Missing price percent"

                        price = float(value[1:-1]) * 0.01
                        method = "market-delta-percent"

                    elif value.startswith('>+') or value.startswith('>-'):
                        if len(value) < 3:
                            return False, "Missing price delta"

                        price = float(value[1:])
                        method = "market-delta-price"
                    else:
                        if len(value) < 2:
                            return False, "Missing price"

                        method = "price"
                        price = float(value[1:])

                elif value.startswith('<'):
                    direction = -1

                    if value.endswith('%'):
                        if len(value) < 3:
                            return False, "Missing price percent"

                        price = float(value[1:-1]) * 0.01
                        method = "market-delta-percent"

                    elif value.startswith('<+') or value.startswith('<-'):
                        if len(value) < 3:
                            return False, "Missing price delta"

                        price = float(value[1:])
                        method = "market-delta-price"
                    else:
                        if len(value) < 2:
                            return False, "Missing price"

                        method = "price"
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
                    cancellation = float(value[2:])
                elif value.startswith('@'):
                    # expiry
                    if ':' in value or '-' in value:
                        # parse a local or UTC datetime
                        expiry = parse_datetime(value[1:]).timestamp()
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
            'method': method,
            'direction': direction,
            'price-src': price_src,
            'cancellation': cancellation
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

        action = 'del-alert'

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
