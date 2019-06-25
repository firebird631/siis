# @date 2019-06-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# terminal region commands and registration

from terminal.command import Command
from strategy.strategy import Strategy
from trader.trader import Trader

from terminal.terminal import Terminal
from common.utils import timeframe_from_str

from instrument.instrument import Instrument


class RangeRegionCommand(Command):
    
    def __init__(self, strategy_service):
        super().__init__('range-region', 'RR')

        self._strategy_service = strategy_service
        self._help = "to manually add a range range on a strategy"

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        appliance = None
        market_id = None
        trade_id = None

        action = "add-region"
        reg = "range"

        low = 0.0
        high = 0.0

        # ie ":RR _ EURUSD 4 1.12 1.15"
        if len(args) != 5:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            if appliance == "_":
                appliance = ""

            trade_id = int(args[2])

            low = float(args[3])
            high = float(args[4])
        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'appliance': appliance,
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'region': reg,
            'low': low,
            'high': high
        })

        return True


class RemoveRegionCommand(Command):

    def __init__(self, strategy_service):
        super().__init__('rmregion', 'DR')

        self._strategy_service = strategy_service
        self._help = "to manually remove a region from a strategy"

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


class RegionInfoCommand(Command):

    def __init__(self, strategy_service):
        super().__init__('region', 'R')

        self._strategy_service = strategy_service
        self._help = "to get region info of a specific strategy"

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

            self._strategy_service.command(Strategy.COMMAND_REGION_INFO, {
                'appliance': appliance,
                'market-id': market_id,
                'region-id': region_id
            })

            return True
        else:
            Terminal.inst().action("Missing or invalid parameters", view='status')
            return False

        return False


def register_region_commands(commands_handler, watcher_service, trader_service, strategy_service):
    cmd = AddRegionCommand(trader_service, strategy_service)
    commands_handler.register(cmd)
    
    cmd = RemoveRegionCommand(trader_service, strategy_service)
    commands_handler.register(cmd)

    cmd = RegionInfoCommand(trader_service, strategy_service)
    commands_handler.register(cmd)
