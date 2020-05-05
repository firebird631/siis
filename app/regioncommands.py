# @date 2019-06-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# terminal region commands and registration

import time

from datetime import datetime

from terminal.command import Command
from strategy.strategy import Strategy
from trader.trader import Trader

from common.utils import timeframe_from_str
from instrument.instrument import Instrument


class RangeRegionCommand(Command):

    SUMMARY = "to manually add a range region on a strategy"
    HELP = (":range-region <appliance-id> <market-id> <low> <high>",
            "optional parameters:",
            "- C@<price> : cancelation price",
            "- @<timestamp|duration> : expiry",
            "- '<timeframe> : timeframe",
            "- L|l|long|LONG|S|s|short|SHORT : direction",
            "- E|e|entry|ENTRY|X|x|exit|EXIT : stage")
    
    def __init__(self, strategy_service):
        super().__init__('range-region', 'RR')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        appliance = None
        market_id = None
        timeframe = -1

        action = "add-region"
        reg = "range"
        stage = 0
        direction = 0
        expiry = 0.0
        created = self._strategy_service.timestamp

        low = 0.0
        high = 0.0
        cancelation = 0.0

        # ie ":RR _ EURUSD 1.12 1.15"
        if len(args) < 4:
            return False, "Missing parameters"

        try:
            appliance, market_id = args[0], args[1]

            low = float(args[2])
            high = float(args[3])

            for value in args[4:]:
                if value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])
                elif value.startswith('C@'):
                    cancelation = float(value[2:])
                elif value.startswith('@'):
                    # expiry
                    if 'T' in value:
                        # as local datetime
                        expiry = datetime.strptime(value[1:], '%Y-%m-%dT%H:%M:%S').timestamp()  # .replace(tzinfo=UTC())
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

        self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'appliance': appliance,
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
            'cancelation': cancelation
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class TrendRegionCommand(Command):

    SUMMARY = "to manually add a trend region on a strategy"
    HELP = (":trend-region <appliance-id> <market-id> <low-a> <high-a> <low-b> <high-b>",
            "optional parameters:",
            "- C@<price> : cancelation price",
            "- @<timestamp|duration> : expiry",
            "- '<timeframe> : timeframe",
            "- L|l|long|LONG|S|s|short|SHORT : direction",
            "- E|e|entry|ENTRY|X|x|exit|EXIT : stage")

    def __init__(self, strategy_service):
        super().__init__('trend-region', 'TR')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        appliance = None
        market_id = None
        timeframe = -1

        action = "add-region"
        reg = "trend"
        stage = 0
        direction = 0
        expiry = 0.0
        created = self._strategy_service.timestamp

        low_a = 0.0
        high_a = 0.0
        low_b = 0.0
        high_b = 0.0
        cancelation = 0.0

        # ie ":TR _ EURUSD 4 1.12 1.15 1.15 1.2"
        if len(args) < 7:
            return False, "Missing parameters"

        try:
            appliance, market_id = args[0], args[1]

            low_a = float(args[2])
            high_a = float(args[3])

            low_b = float(args[4])
            high_b = float(args[5])

            for value in args[6:]:
                if value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])
                elif value.startswith('C@'):
                    cancelation = float(value[2:])
                elif value.startswith('@'):
                    # expiry
                    if 'T' in value:
                        # as local datetime
                        expiry = datetime.strptime(value[1:], '%Y-%m-%dT%H:%M:%S').timestamp()  # .replace(tzinfo=UTC())
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

        self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'appliance': appliance,
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
            'cancelation': cancelation
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class RemoveRegionCommand(Command):

    SUMMARY = "to manually remove a region from a strategy"

    def __init__(self, strategy_service):
        super().__init__('rmregion', 'DR')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        appliance = None
        market_id = None

        action = 'del-region'
        region_id = None        

        # ie ":rmregion _ EURUSD 1"
        if len(args) < 3:
            return False, "Missing parameters"

        try:
            appliance, market_id = args[0], args[1]

            region_id = int(args[2])   
        except Exception:
            return False, "Invalid parameters"

        self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'appliance': appliance,
            'market-id': market_id,
            'action': action,
            'region-id': region_id
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class RegionInfoCommand(Command):

    SUMMARY = "to get region info of a specific strategy"

    def __init__(self, strategy_service):
        super().__init__('region', 'R')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        appliance = None
        market_id = None
        region_id = None

        if len(args) >= 2:
            try:
                appliance, market_id = args[0], args[1]

                if len(args) >= 3:
                    region_id = int(args[2])
                else:
                    region_id = -1

            except Exception:
                return False, "Invalid parameters"

            self._strategy_service.command(Strategy.COMMAND_TRADER_INFO, {
                'appliance': appliance,
                'market-id': market_id,
                'detail': 'region',
                'region-id': region_id
            })

            return True, []
        else:
            return False, "Missing or invalid parameters"

        return False, None

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

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
