# @date 2019-06-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# terminal region commands and registration

from datetime import datetime

from terminal.command import Command
from strategy.strategy import Strategy
from trader.trader import Trader

from terminal.terminal import Terminal
from common.utils import timeframe_from_str

from instrument.instrument import Instrument


class RangeRegionCommand(Command):

    SUMMARY = "to manually add a range region on a strategy"
    
    def __init__(self, strategy_service):
        super().__init__('range-region', 'RR')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        appliance = None
        market_id = None
        trade_id = None
        timeframe = -1

        action = "add-region"
        reg = "range"
        stage = 0
        direction = 0
        expiry = 0

        low = 0.0
        high = 0.0

        # ie ":RR _ EURUSD 1.12 1.15"
        if len(args) < 4:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            if appliance == "_":
                appliance = ""

            low = float(args[2])
            high = float(args[3])

            for value in args[4:]:
                if value.startswith("'"):
                    timeframe = timeframe_from_str(args[4][1:])
                elif value in ("l", "L", "long", "LONG"):
                    direction = 1
                elif value in ("s", "S", "short", "SHORT"):
                    direction = -1
                elif value in ("e", "E", "entry", "ENTRY"):
                    stage = 1
                elif value in ("x", "X", "exit", "EXIT"):
                    stage = -1
                elif value.startswith('@'):
                    # expiry
                    if 'T' in value:
                        # as local datetime
                        expiry = datetime.strptime(value[1:], '%Y-%m-%dT%H:%M:%S').timestamp()  # .replace(tzinfo=UTC())
                    else:
                        # relative to now
                        duration = timeframe_from_str(value[1:])
                        expiry = time.time() + duration

        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'appliance': appliance,
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'region': reg,
            'stage': stage,
            'direction': direction,
            'timeframe': timeframe,
            'expiry': expiry,
            'low': low,
            'high': high
        })

        return True

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            return self.iterate(1, self._strategy_service.appliance(args[0]).symbols_ids(), args, tab_pos, direction)

        return args, 0


class TrendRegionCommand(Command):

    SUMMARY = "to manually add a trend region on a strategy"
    
    def __init__(self, strategy_service):
        super().__init__('trend-region', 'TR')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        appliance = None
        market_id = None
        trade_id = None

        action = "add-region"
        reg = "trend"

        low_a = 0.0
        high_a = 0.0
        low_b = 0.0
        high_b = 0.0

        # ie ":TR _ EURUSD 4 1.12 1.15 1.15 1.2"
        if len(args) != 5:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            if appliance == "_":
                appliance = ""

            trade_id = int(args[2])

            low_a = float(args[3])
            high_a = float(args[4])

            low_b = float(args[5])
            high_b = float(args[6])
        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'appliance': appliance,
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'region': reg,
            'low-a': low_a,
            'high-a': high_a,
            'low-b': low_b,
            'high-b': high_b
        })

        return True

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            return self.iterate(1, self._strategy_service.appliance(args[0]).symbols_ids(), args, tab_pos, direction)

        return args, 0


class RemoveRegionCommand(Command):

    SUMMARY = "to manually remove a region from a strategy"

    def __init__(self, strategy_service):
        super().__init__('rmregion', 'DR')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        appliance = None
        market_id = None
        trade_id = None

        action = 'del-region'
        operation_id = None        

        # ie ":rmregion _ EURUSD 1"
        if len(args) < 3:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            if appliance == "_":
                appliance = ""

            region_id = int(args[2])   
        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'appliance': appliance,
            'market-id': market_id,
            'action': action,
            'region-id': region_id
        })

        return True

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            return self.iterate(1, self._strategy_service.appliance(args[0]).symbols_ids(), args, tab_pos, direction)

        return args, 0


class RegionInfoCommand(Command):

    SUMMARY = "to get region info of a specific strategy"

    def __init__(self, strategy_service):
        super().__init__('region', 'R')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        appliance = None
        market_id = None
        region_id = None

        if len(args) >= 2:
            try:
                appliance, market_id = args[0], args[1]

                if appliance == "_":
                    appliance = ""

                if len(args) >= 3:
                    region_id = int(args[2])
                else:
                    region_id = -1

            except Exception:
                Terminal.inst().action("Invalid parameters", view='status')
                return False

            self._strategy_service.command(Strategy.COMMAND_TRADER_INFO, {
                'appliance': appliance,
                'market-id': market_id,
                'detail': 'region',
                'region-id': region_id
            })

            return True
        else:
            Terminal.inst().action("Missing or invalid parameters", view='status')
            return False

        return False

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            return self.iterate(1, self._strategy_service.appliance(args[0]).symbols_ids(), args, tab_pos, direction)

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
