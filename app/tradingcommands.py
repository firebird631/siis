# @date 2019-06-15
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# terminal trading commands and registration

from terminal.command import Command
from strategy.strategy import Strategy
from trader.trader import Trader

from terminal.terminal import Terminal
from common.utils import timeframe_from_str

from instrument.instrument import Instrument


class PlayCommand(Command):

    def __init__(self, trader_service, strategy_service):
        super().__init__('play', None)

        self._trader_service = trader_service
        self._strategy_service = strategy_service
        self._help = "[traders,apps] to enable traders or appliances."

    def execute(self, args):
        if not args:
            return False

        if args[0] == 'traders':
            self._trader_service.set_activity(True)
            Terminal.inst().action("Activated all traders", view='status')
            return True
        elif args[0] == 'apps':
            self._strategy_service.set_activity(True)
            Terminal.inst().action("Activated all appliances", view='status')
            return True

        return False


class PauseCommand(Command):

    def __init__(self, trader_service, strategy_service):
        super().__init__('pause', None)

        self._trader_service = trader_service
        self._strategy_service = strategy_service
        self._help = "[traders,apps] to disable traders or appliances."

    def execute(self, args):
        if not args:
            return False

        if args[0] == 'traders':
            self._trader_service.set_activity(False)
            Terminal.inst().action("Paused all traders", view='status')
            return True
        elif args[0] == 'apps':
            self._strategy_service.set_activity(False)
            Terminal.inst().action("Paused all appliances", view='status')
            return True

        return False


class InfoCommand(Command):

    def __init__(self, trader_service, strategy_service):
        super().__init__('info', None)

        self._trader_service = trader_service
        self._strategy_service = strategy_service
        self._help = "[traders,apps] to get info on traders or appliances."

    def execute(self, args):
        if not args:
            return False

        if args[0] == 'traders':
            self._trader_service.command(Trader.COMMAND_INFO, {})
            return True
        elif args[0] == 'apps':
            self._strategy_service.command(Strategy.COMMAND_INFO, {})
            return True

        return False


class LongCommand(Command):

    def __init__(self, strategy_service):
        super().__init__('long', 'L')

        self._strategy_service = strategy_service
        self._help = "to manually create to a new trade in LONG direction"

    def execute(self, args):
        if not args:
            return False

        # ie: ":long altbtc:BTCUSDT L@8500 SL@8300 TP@9600 1.0"
        appliance = None
        market_id = None

        # direction base on command name
        direction = 1
        method = 'market'
        price = None
        stop_loss = 0.0
        take_profit = 0.0
        quantity_rate = 1.0
        timeframe = Instrument.TF_4HOUR

        if len(args) < 1:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0].split(':')

            for value in args[1:]:
                if not value:
                    continue

                if value.startswith("L@"):
                    method = 'limit'
                    price = float(value[2:])
                elif value.startswith("T@"):
                    method = 'trigger'
                    price = float(value[2:])
                elif value.startswith("SL@"):
                    stop_loss = float(value[3:])
                elif value.startswith("TP@"):
                    take_profit = float(value[3:])
                elif value.startswith("'"):
                    take_profit = timeframe_from_str(value[1:])
                elif value.startswith("*"):
                    quantity_rate = float(value[1:])
                elif value.endswith("%"):
                    quantity_rate = float(value[:-1]) * 0.01

        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        if price and stop_loss and stop_loss > price:
            Terminal.inst().action("Stop-loss must be lesser than limit price", view='status')
            return False

        if price and take_profit and take_profit < price:
            Terminal.inst().action("Stop-loss must be greater than limit price", view='status')
            return False

        if quantity_rate <= 0.0:
            Terminal.inst().action("Quantity must be non empty", view='status')
            return False


        self._strategy_service.command(Strategy.COMMAND_TRADE_ENTRY, {
            'appliance': appliance,
            'market-id': market_id,
            'direction': direction,
            'price': price,
            'method': method,
            'quantity-rate': quantity_rate,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'timeframe': timeframe
        })

        return True


class ShortCommand(Command):

    def __init__(self, strategy_service):
        super().__init__('short', 'S')

        self._strategy_service = strategy_service
        self._help = "to manually create to a new trade in SHORT direction"

    def execute(self, args):
        if not args:
            return False

        # ie: ":long altbtc:BTCUSDT L@8500 SL@8300 TP@9600 1.0"
        appliance = None
        market_id = None

        # direction base on command name
        direction = -1
        method = 'market'
        price = None
        stop_loss = 0.0
        take_profit = 0.0
        quantity_rate = 1.0
        timeframe = Instrument.TF_4HOUR

        if len(args) < 1:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0].split(':')

            for value in args[1:]:
                if not value:
                    continue

                if value.startswith("L@"):
                    method = 'limit'
                    price = float(value[2:])
                elif value.startswith("T@"):
                    method = 'trigger'
                    price = float(value[2:])
                elif value.startswith("SL@"):
                    stop_loss = float(value[3:])
                elif value.startswith("TP@"):
                    take_profit = float(value[3:])
                elif value.startswith("'"):
                    take_profit = timeframe_from_str(value[1:])
                elif value.startswith("*"):
                    quantity_rate = float(value[1:])
                elif value.endswith("%"):
                    quantity_rate = float(value[:-1]) * 0.01

        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        if price and stop_loss and stop_loss < price:
            Terminal.inst().action("Stop-loss must be greater than limit price", view='status')
            return False

        if price and take_profit and take_profit > price:
            Terminal.inst().action("Stop-loss must be less than limit price", view='status')
            return False

        if quantity_rate <= 0.0:
            Terminal.inst().action("Quantity must be non empty", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADE_ENTRY, {
            'appliance': appliance,
            'market-id': market_id,
            'direction': direction,
            'price': price,
            'method': method,
            'quantity-rate': quantity_rate,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'timeframe': timeframe
        })

        return True


class CloseCommand(Command):

    def __init__(self, strategy_service):
        super().__init__('close', 'C')

        self._strategy_service = strategy_service
        self._help = "to manually close a managed trade at market or limit"

    def execute(self, args):
        if not args:
            return False

        appliance = None
        market_id = None
        trade_id = None
        action = "close"

        method = 'market'
        price = None

        # ie ":close :EURUSD 5 1.12"
        if not 2 <= len(args) <= 3:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0].split(':')
            trade_id = int(args[1])

            if len(args) == 3:
                price = float(args[2])
                method = 'limit'
   
        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADE_EXIT, {
            'appliance': appliance,
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'method': method,
            'price': price
        })

        return True


class DynamicStopLossOperationCommand(Command):
    
    def __init__(self, strategy_service):
        super().__init__('dynamic-stop-loss', 'DSL')

        self._strategy_service = strategy_service
        self._help = "to manually add a dynamic-stop-loss operation on a trade"

    def execute(self, args):
        if not args:
            return False

        appliance = None
        market_id = None
        trade_id = None

        action = "add-op"
        op = "dynamic-stop-loss"

        trigger = 0.0
        stop_loss = 0.0

        # ie ":DSL :EURUSD 4 1.12 1.15"
        if len(args) != 4:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0].split(':')
            trade_id = int(args[1])

            trigger = float(args[2])
            stop_loss = float(args[3])
        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'appliance': appliance,
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'operation': op,
            'trigger': trigger,
            'stop-loss': stop_loss
        })

        return True


class RemoveOperationCommand(Command):

    def __init__(self, strategy_service):
        super().__init__('del', 'D')

        self._strategy_service = strategy_service
        self._help = "to manually remove an operation from a trade"

    def execute(self, args):
        if not args:
            return False

        appliance = None
        market_id = None
        trade_id = None

        action = 'del-op'
        operation_id = None        

        # ie ":SL :EURUSD 1 5"
        if len(args) < 3:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0].split(':')
            trade_id = int(args[1])
            operation_id = int(args[2])   
        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'appliance': appliance,
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'operation-id': operation_id
        })

        return True


class ModifyStopLossCommand(Command):

    def __init__(self, strategy_service):
        super().__init__('stop-loss', 'SL')

        self._strategy_service = strategy_service
        self._help = "to manually modify the stop-loss of a trade"

    def execute(self, args):
        if not args:
            return False

        appliance = None
        market_id = None
        trade_id = None

        action = 'stop-loss'
        stop_loss = 0.0

        # ie ":SL :EURUSD 1 1.10"
        if len(args) < 3:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0].split(':')
            trade_id = int(args[1])
            stop_loss = float(args[2])   
        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'appliance': appliance,
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'stop-loss': stop_loss
        })

        return True


class ModifyTakeProfitCommand(Command):

    def __init__(self, strategy_service):
        super().__init__('take-profit', 'TP')

        self._strategy_service = strategy_service
        self._help = "to manually modify the take-profit of a trade"

    def execute(self, args):
        if not args:
            return False

        appliance = None
        market_id = None
        trade_id = None

        action = 'take-profit'
        take_profit = 0.0

        # ie ":TP :EURUSD 1 1.15"
        if len(args) < 3:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0].split(':')
            trade_id = int(args[1])
            take_profit = float(args[2])   
        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'appliance': appliance,
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'take-profit': take_profit
        })

        return True


class TradeInfoCommand(Command):

    def __init__(self, strategy_service):
        super().__init__('trade', 'T')

        self._strategy_service = strategy_service
        self._help = "to get operation info of a specific trade"

    def execute(self, args):
        if not args:
            return False

        appliance = None
        market_id = None
        trade_id = None

        if len(args) >= 1:
            try:
                appliance, market_id = args[0].split(':')

                if len(args) >= 2:
                    trade_id = int(args[1])
                else:
                    trade_id = -1

            except Exception:
                Terminal.inst().action("Invalid parameters", view='status')
                return False

            self._strategy_service.command(Strategy.COMMAND_TRADE_INFO, {
                'appliance': appliance,
                'market-id': market_id,
                'trade-id': trade_id
            })

            return True
        else:
            Terminal.inst().action("Missing or invalid parameters", view='status')
            return False

        return False


def register_trading_commands(commands_handler, watcher_service, trader_service, strategy_service):
    cmd = PlayCommand(trader_service, strategy_service)
    commands_handler.register(cmd)
    
    cmd = PauseCommand(trader_service, strategy_service)
    commands_handler.register(cmd)

    cmd = InfoCommand(trader_service, strategy_service)
    commands_handler.register(cmd)

    cmd = LongCommand(strategy_service)
    commands_handler.register(cmd)

    cmd = ShortCommand(strategy_service)
    commands_handler.register(cmd)

    cmd = CloseCommand(strategy_service)
    commands_handler.register(cmd)

    cmd = RemoveOperationCommand(strategy_service)
    commands_handler.register(cmd)

    cmd = ModifyStopLossCommand(strategy_service)
    commands_handler.register(cmd)

    cmd = ModifyTakeProfitCommand(strategy_service)
    commands_handler.register(cmd)    

    cmd = TradeInfoCommand(strategy_service)
    commands_handler.register(cmd)

    #
    # trade operations
    #

    cmd = DynamicStopLossOperationCommand(strategy_service)
    commands_handler.register(cmd)
