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

# @todo replace Terminal... by a return str in addition of the status

class PlayCommand(Command):

    SUMMARY = "[traders,apps] <[appliance-id,trader-id]> <appliance-market-id> to enable trader(s) or appliance(s)."

    def __init__(self, trader_service, strategy_service):
        super().__init__('play', None)

        self._trader_service = trader_service
        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        if args[0] == 'traders':
            if len(args) == 1:
                self._trader_service.set_activity(True)
                Terminal.inst().action("Activated all traders", view='status')
                return True
            elif len(args) == 2:
                # @todo specific trader
                return False

        elif args[0] == 'apps':
            if len(args) == 1:
                self._strategy_service.set_activity(True)
                Terminal.inst().action("Activated any markets for all appliances", view='status')
                return True
            elif len(args) == 2:
                appliance = self._strategy_service.appliance(args[1])
                if appliance:
                    appliance.set_activity(True)
                    Terminal.inst().action("Activated any markets for appliances %s" % args[1], view='status')
                return True
            elif len(args) == 3:
                appliance = self._strategy_service.appliance(args[1])
                if appliance:
                    appliance.set_activity(True, args[2])
                    Terminal.inst().action("Activated instrument %s for appliances %s" % (args[2], args[1]), view='status')
                return True

        return False

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, ['apps', 'traders'], args, tab_pos, direction)

        elif len(args) <= 2:
            # appliance/trader
            if args[0] == "apps":
                return self.iterate(1, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)
            elif args[0] == "traders":
                return self.iterate(1, self._trader_service.traders_names(), args, tab_pos, direction)

        elif len(args) <= 3:
            if args[0] == 'apps':
                # instrument
                appliance = self._strategy_service.appliance(args[1])
                if appliance:
                    return self.iterate(2, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class PauseCommand(Command):

    SUMMARY = "[traders,apps] <[appliance-id,trader-id]> <appliance-market-id> to disable trader(s) or appliance(s)."

    def __init__(self, trader_service, strategy_service):
        super().__init__('pause', None)

        self._trader_service = trader_service
        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        if args[0] == 'traders':
            if len(args) == 1:
                self._trader_service.set_activity(False)
                Terminal.inst().action("Paused all traders", view='status')
                return True
            elif len(args) == 2:
                # @todo specific trader
                return False
        elif args[0] == 'apps':
            if len(args) == 1:
                self._strategy_service.set_activity(False)
                Terminal.inst().action("Paused all any market for all appliances", view='status')
                return True
            elif len(args) == 2:
                appliance = self._strategy_service.appliance(args[1])
                if appliance:
                    appliance.set_activity(False)
                    Terminal.inst().action("Paused any markets for appliances %s" % args[1], view='status')
                return True
            elif len(args) == 3:
                appliance = self._strategy_service.appliance(args[1])
                if appliance:
                    appliance.set_activity(False, args[2])
                    Terminal.inst().action("Paused instrument %s for appliances %s" % (args[2], args[1]), view='status')
                return True

        return False

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, ['apps', 'traders'], args, tab_pos, direction)

        elif len(args) <= 2:
            # appliance/trader
            if args[0] == "apps":
                return self.iterate(1, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)
            elif args[0] == "traders":
                return self.iterate(1, self._trader_service.traders_names(), args, tab_pos, direction)

        elif len(args) <= 3:
            if args[0] == 'apps':
                # instrument
                appliance = self._strategy_service.appliance(args[1])
                if appliance:
                    return self.iterate(2, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class InfoCommand(Command):

    SUMMARY = "[traders,apps] <[appliance-id,trader-id]> <appliance-market-id> to get info on traders or appliances."

    def __init__(self, trader_service, strategy_service):
        super().__init__('info', None)

        self._trader_service = trader_service
        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        if args[0] == 'traders':
            if len(args) == 1:
                self._trader_service.command(Trader.COMMAND_INFO, {})
                return True
            elif len(args) == 2:
                self._strategy_service.command(Trader.COMMAND_INFO, {'trader': args[1]})
                return False
            elif len(args) == 3:
                self._strategy_service.command(Trader.COMMAND_INFO, {'trader': args[1], 'market-id': args[2]})
                return False
        elif args[0] == 'apps':
            if len(args) == 1:
                self._strategy_service.command(Strategy.COMMAND_INFO, {})
                return True
            elif len(args) == 2:
                self._strategy_service.command(Strategy.COMMAND_INFO, {'appliance': args[1]})
                return True
            elif len(args) == 3:
                self._strategy_service.command(Strategy.COMMAND_INFO, {'appliance': args[1], 'market-id': args[2]})
                return True

        return False

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, ['apps', 'traders'], args, tab_pos, direction)

        elif len(args) <= 2:
            # appliance/trader
            if args[0] == "apps":
                return self.iterate(1, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)
            elif args[0] == "traders":
                return self.iterate(1, self._trader_service.traders_names(), args, tab_pos, direction)

        elif len(args) <= 3:
            if args[0] == 'apps':
                # instrument
                appliance = self._strategy_service.appliance(args[1])
                if appliance:
                    return self.iterate(2, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class LongCommand(Command):

    SUMMARY = "to manually create to a new trade in LONG direction"

    def __init__(self, strategy_service):
        super().__init__('long', 'L')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        # ie: ":long altbtc BTCUSDT L@8500 SL@8300 TP@9600 1.0"
        appliance = None
        market_id = None

        # direction base on command name
        direction = 1
        method = 'market'
        limit_price = None
        trigger_price = None
        stop_loss = 0.0
        take_profit = 0.0
        quantity_rate = 1.0
        timeframe = Instrument.TF_4HOUR

        if len(args) < 2:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            for value in args[2:]:
                if not value:
                    continue

                if value.startswith("L@"):
                    method = 'limit'
                    limit_price = float(value[2:])
                elif value.startswith("T@"):
                    method = 'trigger'
                    trigger_price = float(value[2:])
                elif value.startswith("SL@"):
                    stop_loss = float(value[3:])
                elif value.startswith("TP@"):
                    take_profit = float(value[3:])
                elif value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])
                elif value.startswith("*"):
                    quantity_rate = float(value[1:])
                elif value.endswith("%"):
                    quantity_rate = float(value[:-1]) * 0.01

        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        if limit_price and stop_loss and stop_loss > limit_price:
            Terminal.inst().action("Stop-loss must be lesser than limit price", view='status')
            return False

        if limit_price and take_profit and take_profit < limit_price:
            Terminal.inst().action("Take-profit must be greater than limit price", view='status')
            return False

        if quantity_rate <= 0.0:
            Terminal.inst().action("Quantity must be non empty", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADE_ENTRY, {
            'appliance': appliance,
            'market-id': market_id,
            'direction': direction,
            'limit-price': limit_price,
            'trigger-price': trigger_price,
            'method': method,
            'quantity-rate': quantity_rate,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'timeframe': timeframe
        })

        return True

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class ShortCommand(Command):

    SUMMARY = "to manually create to a new trade in SHORT direction"
   
    def __init__(self, strategy_service):
        super().__init__('short', 'S')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        # ie: ":long altbtc BTCUSDT L@8500 SL@8300 TP@9600 1.0"
        appliance = None
        market_id = None

        # direction base on command name
        direction = -1
        method = 'market'
        limit_price = None
        trigger_price = None
        stop_loss = 0.0
        take_profit = 0.0
        quantity_rate = 1.0
        timeframe = Instrument.TF_4HOUR

        if len(args) < 2:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            for value in args[2:]:
                if not value:
                    continue

                if value.startswith("L@"):
                    method = 'limit'
                    limit_price = float(value[2:])
                elif value.startswith("T@"):
                    method = 'trigger'
                    trigger_price = float(value[2:])
                elif value.startswith("SL@"):
                    stop_loss = float(value[3:])
                elif value.startswith("TP@"):
                    take_profit = float(value[3:])
                elif value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])
                elif value.startswith("*"):
                    quantity_rate = float(value[1:])
                elif value.endswith("%"):
                    quantity_rate = float(value[:-1]) * 0.01

        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        if limit_price and stop_loss and stop_loss < limit_price:
            Terminal.inst().action("Stop-loss must be greater than limit price", view='status')
            return False

        if limit_price and take_profit and take_profit > limit_price:
            Terminal.inst().action("Take-profit must be lesser than limit price", view='status')
            return False

        if quantity_rate <= 0.0:
            Terminal.inst().action("Quantity must be non empty", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADE_ENTRY, {
            'appliance': appliance,
            'market-id': market_id,
            'direction': direction,
            'limit-price': limit_price,
            'trigger-price': trigger_price,
            'method': method,
            'quantity-rate': quantity_rate,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'timeframe': timeframe
        })

        return True

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class CloseCommand(Command):

    SUMMARY = "to manually close a managed trade at market or limit"

    def __init__(self, strategy_service):
        super().__init__('close', 'C')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        appliance = None
        market_id = None
        trade_id = None
        action = "close"

        # ie ":close _ EURUSD 5"
        if len(args) != 3:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]
            trade_id = int(args[2])

        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADE_EXIT, {
            'appliance': appliance,
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action
        })

        return True

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class DynamicStopLossOperationCommand(Command):
    
    SUMMARY = "to manually add a dynamic-stop-loss operation on a trade"
    HELP = ("<appliance-identifier> <market-id> <trigger-price> <stop-loss-price>",)

    def __init__(self, strategy_service):
        super().__init__('dynamic-stop-loss', 'DSL')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        appliance = None
        market_id = None
        trade_id = None

        action = "add-op"
        op = "dynamic-stop-loss"

        trigger = 0.0
        stop_loss = 0.0

        # ie ":DSL _ EURUSD 4 1.12 1.15"
        if len(args) != 5:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            trade_id = int(args[2])

            trigger = float(args[3])
            stop_loss = float(args[4])
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

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class RemoveOperationCommand(Command):

    SUMMARY = "to manually remove an operation from a trade"

    def __init__(self, strategy_service):
        super().__init__('del', 'D')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        appliance = None
        market_id = None
        trade_id = None

        action = 'del-op'
        operation_id = None        

        # ie ":SL _ EURUSD 1 5"
        if len(args) < 4:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            trade_id = int(args[2])
            operation_id = int(args[3])   
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

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class ModifyStopLossCommand(Command):

    SUMMARY = "to manually modify the stop-loss of a trade"
   
    def __init__(self, strategy_service):
        super().__init__('stop-loss', 'SL')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False

        appliance = None
        market_id = None
        trade_id = None

        action = 'stop-loss'
        stop_loss = 0.0

        # ie ":SL _ EURUSD 1 1.10"
        if len(args) < 4:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            trade_id = int(args[2])
            stop_loss = float(args[3])   
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

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class ModifyTakeProfitCommand(Command):

    SUMMARY = "to manually modify the take-profit of a trade"

    def __init__(self, strategy_service):
        super().__init__('take-profit', 'TP')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        appliance = None
        market_id = None
        trade_id = None

        action = 'take-profit'
        take_profit = 0.0

        # ie ":TP _ EURUSD 1 1.15"
        if len(args) < 4:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            trade_id = int(args[2])
            take_profit = float(args[3])
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
    
    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class TradeInfoCommand(Command):

    SUMMARY = "to get operation info of a specific trade"

    def __init__(self, strategy_service):
        super().__init__('trade', 'T')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        appliance = None
        market_id = None
        trade_id = None

        if len(args) >= 2:
            try:
                appliance, market_id = args[0], args[1]

                if len(args) >= 3:
                    trade_id = int(args[2])
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

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class AssignCommand(Command):

    SUMMARY = "to manually assign a quantity of asset to a new trade in LONG direction"

    def __init__(self, strategy_service):
        super().__init__('assign', 'AS')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        # ie: ":assign altbtc BTCUSDT EP@8500 SL@8300 TP@9600 0.521"
        appliance = None
        market_id = None

        # direction base on command name
        direction = 1
        entry_price = None
        stop_loss = 0.0
        take_profit = 0.0
        quantity = 0.0
        timeframe = Instrument.TF_4HOUR

        if len(args) < 4:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            for value in args[2:]:
                if not value:
                    continue

                if value.startswith("EP@"):
                    entry_price = float(value[3:])
                elif value.startswith("SL@"):
                    stop_loss = float(value[3:])
                elif value.startswith("TP@"):
                    take_profit = float(value[3:])
                elif value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])
                else:
                    quantity = float(value)

        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        if entry_price <= 0.0:
            Terminal.inst().action("Entry price must be specified", view='status')
            return False

        if stop_loss and stop_loss > entry_price:
            Terminal.inst().action("Stop-loss must be lesser than entry price", view='status')
            return False

        if take_profit and take_profit < entry_price:
            Terminal.inst().action("Take-profit must be greater than entry price", view='status')
            return False

        if quantity <= 0.0:
            Terminal.inst().action("Quantity must be specified", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADE_ASSIGN, {
            'appliance': appliance,
            'market-id': market_id,
            'direction': direction,
            'entry-price': entry_price,
            'quantity': quantity,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'timeframe': timeframe
        })

        return True

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class ChartCommand(Command):

    SUMMARY = "to display a chat for a specific stragegy and market"
    
    def __init__(self, strategy_service, monitor_service):
        super().__init__('chart', 'V')

        self._strategy_service = strategy_service
        self._monitor_service = monitor_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        # ie: ":chart altbtc BTCUSDT"
        appliance = None
        market_id = None

        # optionnal timeframe (could depend of the strategy)
        timeframe = None

        if len(args) < 2:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            if len(args) == 3:
                timeframe = timeframe_from_str(args[2])

        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADER_CHART, {
            'appliance': appliance,
            'market-id': market_id,
            'timeframe': timeframe,
            'monitor-url': self._monitor_service.url()
        })

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


class UserSaveCommand(Command):

    # @todo
    SUMMARY = "to save user data now (strategy traders states, options, regions, trades)"

    def __init__(self, strategy_service):
        super().__init__('save', 's')

        self._strategy_service = strategy_service

    def execute(self, args):
        return False


class SetQuantityCommand(Command):

    SUMMARY = "to change the traded quantity per market of a strategy"
    
    def __init__(self, strategy_service):
        super().__init__('setquantity', 'SETQTY')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        # ie: ":setquantity altbtc BTCUSDT 1000"
        appliance = None
        market_id = None

        if len(args) < 3:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]
            quantity = float(args[2])

        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        if quantity <= 0.0:
            Terminal.inst().action("Invalid quantity", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'appliance': appliance,
            'market-id': market_id,
            'action': "set-quantity",
            'quantity': quantity
        })

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._strategy_service.appliances_identifiers(), args, tab_pos, direction)

        elif len(args) <= 2:
            appliance = self._strategy_service.appliance(args[0])
            if appliance:
                return self.iterate(1, appliance.symbols_ids(), args, tab_pos, direction)

        return args, 0


def register_trading_commands(commands_handler, trader_service, strategy_service, monitor_service):
    #
    # global
    #

    commands_handler.register(PlayCommand(trader_service, strategy_service))
    commands_handler.register(PauseCommand(trader_service, strategy_service))
    commands_handler.register(InfoCommand(trader_service, strategy_service))
    commands_handler.register(ChartCommand(strategy_service, monitor_service))
    commands_handler.register(UserSaveCommand(strategy_service))
    commands_handler.register(SetQuantityCommand(strategy_service))

    #
    # order
    #

    commands_handler.register(LongCommand(strategy_service))
    commands_handler.register(ShortCommand(strategy_service))
    commands_handler.register(CloseCommand(strategy_service))
    commands_handler.register(ModifyStopLossCommand(strategy_service))
    commands_handler.register(ModifyTakeProfitCommand(strategy_service))
    commands_handler.register(AssignCommand(strategy_service))

    #
    # trade operations
    #

    commands_handler.register(TradeInfoCommand(strategy_service))
    commands_handler.register(RemoveOperationCommand(strategy_service))
    commands_handler.register(DynamicStopLossOperationCommand(strategy_service))
