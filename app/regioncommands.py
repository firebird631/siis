# @date 2019-06-25
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# terminal region commands and registration

from terminal.command import Command
from strategy.strategy import Strategy

from common.utils import timeframe_from_str, parse_datetime


class RangeRegionCommand(Command):

    SUMMARY = "to manually add a range region on a strategy"
    HELP = (":range-region <market-id> <low> <high>",
            "optional parameters:",
            "- [C]@<price> : cancellation price",
            "- [@]<timestamp|duration> : expiry",
            "- [']<timeframe> : timeframe",
            "- [L|l|long|LONG|S|s|short|SHORT] : direction",
            "- [E|e|entry|ENTRY|X|x|exit|EXIT] : stage")
    
    def __init__(self, strategy_service):
        super().__init__('range-region', 'RR')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        timeframe = 0.0

        action = "add-region"
        reg = "range"
        stage = 0
        direction = 0
        expiry = 0.0
        created = self._strategy_service.timestamp

        cancellation = 0.0

        # ie ":RR EURUSD 1.12 1.15"
        if len(args) < 3:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            low = float(args[1])
            high = float(args[2])

            for value in args[3:]:
                if value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])
                elif value.startswith('C@'):
                    cancellation = float(value[2:])
                elif value.startswith('@'):
                    # expiry
                    if ':' in value or '-' in value:
                        # as local datetime
                        expiry = parse_datetime(value[1:]).timestamp()
                    else:
                        # relative to now
                        duration = timeframe_from_str(value[1:])
                        expiry = created + duration
                elif value in ("l", "L", "long", "LONG"):
                    direction = 1
                elif value in ("s", "S", "short", "SHORT"):
                    direction = -1
                elif value in ("e", "E", "entry", "ENTRY"):
                    stage = 1
                elif value in ("x", "X", "exit", "EXIT"):
                    stage = -1

        except Exception:
            return False, "Invalid parameters"

        results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'market-id': market_id,
            'action': action,
            'region': reg,
            'created': created,
            'stage': stage,
            'direction': direction,
            'timeframe': timeframe,
            'expiry': expiry,
            'low': low,
            'high': high,
            'cancellation': cancellation
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class TrendRegionCommand(Command):

    SUMMARY = "to manually add a trend region on a strategy"
    HELP = (":trend-region <market-id> <low-a> <high-a> <low-b> <high-b>",
            "optional parameters:",
            "- [C@]<price> : cancellation price",
            "- [@]<timestamp|duration> : expiry",
            "- [']<timeframe> : timeframe",
            "- [L|l|long|LONG|S|s|short|SHORT] : direction",
            "- [E|e|entry|ENTRY|X|x|exit|EXIT] : stage")

    def __init__(self, strategy_service):
        super().__init__('trend-region', 'TR')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        timeframe = 0.0

        action = "add-region"
        reg = "trend"
        stage = 0
        direction = 0
        expiry = 0.0
        created = self._strategy_service.timestamp

        cancellation = 0.0

        # ie ":TR EURUSD 1.12 1.15 1.15 1.2"
        if len(args) < 6:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            low_a = float(args[1])
            high_a = float(args[2])

            low_b = float(args[3])
            high_b = float(args[4])

            for value in args[5:]:
                if value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])
                elif value.startswith('C@'):
                    cancellation = float(value[2:])
                elif value.startswith('@'):
                    # expiry
                    if ':' in value or '-' in value:
                        # as local datetime
                        expiry = parse_datetime(value[1:]).timestamp()
                    else:
                        # relative to now
                        duration = timeframe_from_str(value[1:])
                        expiry = created + duration
                elif value in ("l", "L", "long", "LONG"):
                    direction = 1
                elif value in ("s", "S", "short", "SHORT"):
                    direction = -1
                elif value in ("e", "E", "entry", "ENTRY"):
                    stage = 1
                elif value in ("x", "X", "exit", "EXIT"):
                    stage = -1

        except Exception:
            return False, "Invalid parameters"

        results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'market-id': market_id,
            'action': action,
            'region': reg,
            'created': created,
            'stage': stage,
            'direction': direction,
            'timeframe': timeframe,
            'expiry': expiry,
            'low-a': low_a,
            'high-a': high_a,
            'low-b': low_b,
            'high-b': high_b,
            'cancellation': cancellation
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class RemoveRegionCommand(Command):

    SUMMARY = "to manually remove a region from a strategy"

    def __init__(self, strategy_service):
        super().__init__('rmregion', 'DR')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        action = 'del-region'

        # ie ":rmregion EURUSD 1"
        if len(args) < 2:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            region_id = int(args[1])   
        except Exception:
            return False, "Invalid parameters"

        results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'market-id': market_id,
            'action': action,
            'region-id': region_id
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class RegionInfoCommand(Command):

    SUMMARY = "to get region info of a specific strategy"

    def __init__(self, strategy_service):
        super().__init__('region', 'R')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        if len(args) >= 1:
            try:
                market_id = args[0]

                if len(args) >= 2:
                    region_id = int(args[1])
                else:
                    region_id = -1

            except Exception:
                return False, "Invalid parameters"

            results = self._strategy_service.command(Strategy.COMMAND_TRADER_INFO, {
                'market-id': market_id,
                'detail': 'region',
                'region-id': region_id
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


def register_region_commands(commands_handler, strategy_service):
    cmd = RangeRegionCommand(strategy_service)
    commands_handler.register(cmd)

    cmd = TrendRegionCommand(strategy_service)
    commands_handler.register(cmd)

    cmd = RemoveRegionCommand(strategy_service)
    commands_handler.register(cmd)

    cmd = RegionInfoCommand(strategy_service)
    commands_handler.register(cmd)
