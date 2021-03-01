# @date 2019-06-15
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# terminal trading commands and registration

import re

from terminal.command import Command
from strategy.strategy import Strategy
from notifier.notifier import Notifier
from trader.trader import Trader

from common.utils import timeframe_from_str
from instrument.instrument import Instrument

# @todo ClosePositionCommand, CloseAllPositionCommand

class PlayCommand(Command):

    SUMMARY = "[strategy,notifiers] <empty,notifier-id]> <market-id> to enable strategy-trader(s) or notifiers(s)."

    def __init__(self, strategy_service, notifier_service):
        super().__init__('play', None)

        self._strategy_service = strategy_service
        self._notifier_service = notifier_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        if args[0] == 'strategy':
            if len(args) == 1:
                self._strategy_service.set_activity(True)
                return True, "Activated any instruments for strategy"

            elif len(args) == 2:
                strategy = self._strategy_service.strategy()
                if strategy:
                    strategy.set_activity(True, args[1])
                    return True, "Activated instrument %s" % args[1]

        elif args[0] == 'notifiers':
            if len(args) == 1:
                self.notifier_service.set_activity(True)
                return True, "Activated all notifiers"

            elif len(args) == 2:
                notifier = self._notifier_service.notifier(args[1])
                if notifier:
                    notifier.set_activity(True)
                    return True, "Activated notifier %s" % args[1]

        return False, None

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, ['strategy', 'notifiers'], args, tab_pos, direction)

        elif len(args) <= 2:
            if args[0] == "strategy":
                # instrument
                strategy = self._strategy_service.strategy()
                if strategy:
                    return self.iterate(1, strategy.symbols_ids(), args, tab_pos, direction)

            elif args[0] == "notifiers":
                return self.iterate(1, self._notifier_service.notifiers_identifiers(), args, tab_pos, direction)

        return args, 0


class PauseCommand(Command):

    SUMMARY = "[strategy,notifiers] <empty,notifier-id]> <market-id> to disable strategy-trader(s) or notifiers(s)."

    def __init__(self, strategy_service, notifier_service):
        super().__init__('pause', None)

        self._strategy_service = strategy_service
        self._notifier_service = notifier_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        if args[0] == 'strategy':
            if len(args) == 1:
                self._strategy_service.set_activity(False)
                return True, "Paused any instruments for strategy"

            elif len(args) == 2:
                strategy = self._strategy_service.strategy()
                if strategy:
                    strategy.set_activity(False, args[1])
                    return True, "Paused instrument %s" % args[1]

        elif args[0] == 'notifiers':
            if len(args) == 1:
                self.notifier_service.set_activity(False)
                return True, "Paused all notifiers"
                
            elif len(args) == 2:
                notifier = self._notifier_service.notifier(args[1])
                if notifier:
                    notifier.set_activity(False)
                    return True, "Paused notifier %s" % args[1]

        return False, None

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, ['strategy', 'notifiers'], args, tab_pos, direction)

        elif len(args) <= 2:
            if args[0] == "strategy":
                # instrument
                strategy = self._strategy_service.strategy()
                if strategy:
                    return self.iterate(1, strategy.symbols_ids(), args, tab_pos, direction)

            elif args[0] == "notifiers":
                return self.iterate(1, self._notifier_service.notifiers_identifiers(), args, tab_pos, direction)

        return args, 0


class InfoCommand(Command):

    SUMMARY = "[strategy,trader,notifiers] <empty,notifier-id]> <market-id> to get info on strategy-trader(s), trader or notifier(s)."

    def __init__(self, strategy_service, notifier_service):
        super().__init__('info', None)

        self._strategy_service = strategy_service
        self._notifier_service = notifier_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters. Need at at least strategy or notifiers."

        if args[0] == 'strategy':
            if len(args) == 1:
                self._strategy_service.command(Strategy.COMMAND_INFO, {})
                return True, []

            elif len(args) == 2:
                self._strategy_service.command(Strategy.COMMAND_INFO, {'market-id': args[1]})
                return True, []

        elif args[0] == 'notifiers':
            if len(args) == 1:
                self._notifier_service.command(Notifier.COMMAND_INFO, {})
                return True, []

            elif len(args) == 2:
                self._notifier_service.command(Notifier.COMMAND_INFO, {'notifier': args[1]})
                return True, []

        return False, None

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, ['strategy', 'notifiers'], args, tab_pos, direction)

        elif len(args) <= 2:
            if args[0] == "strategy":
                # instrument
                strategy = self._strategy_service.strategy()
                if strategy:
                    return self.iterate(1, strategy.symbols_ids(), args, tab_pos, direction)

            elif args[0] == "notifiers":
                return self.iterate(1, self._notifier_service.notifiers_identifiers(), args, tab_pos, direction)

        return args, 0


class SetAffinityCommand(Command):

    SUMMARY = "<market-id> to modify the affinity per market."

    def __init__(self, strategy_service):
        super().__init__('set-affinity', 'SETAFF')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters. Need at least affinity."

        action = "set-affinity"
        market_id = None
        affinity = 0

        is_int = True

        try:
            int(args[0])
        except ValueError:
            is_int = False

        if is_int:
            try:
                affinity = int(args[0])
            except ValueError:
                return False, "Invalid affinity format"
        else:
            market_id = args[0]

            try:
                affinity = int(args[1])
            except ValueError:
                return False, "Invalid affinity format"

        if market_id:
            self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
                'market-id': market_id,
                'action': action,
                'affinity': affinity
            })
        else:
            self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY_ALL, {
                'action': action,
                'affinity': affinity
            })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            if len(args) == 1:
                is_int = True

                try:
                    int(args[0])
                except ValueError:
                    is_int = False

                if is_int:
                    return args, 0

            # instrument
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class SetOptionCommand(Command):

    SUMMARY = "any or specify <market-id> to modify the option per market."

    INTEGER_RE = re.compile(r'^[+-]{0,1}[0-9]+$')
    FLOAT_RE = re.compile(r'(?i)^\s*[+-]?(?:inf(inity)?|nan|(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)\s*$')

    def __init__(self, strategy_service):
        super().__init__('set-option', 'SETOPT')

        self._strategy_service = strategy_service

    def execute(self, args):
        if len(args) < 2 or len(args) > 3:
            return False, "Missing parameters. Need at least option and value."

        action = "set-option"
        market_id = None
        option = None
        value = None

        def convert_value(v):
            if v is None:
                # undefined
                return None

            if len(v) == 0:
                # empty string
                return ""

            if SetOptionCommand.FLOAT_RE.match(v) is not None:
                # float ?
                try:
                    return float(v)
                except ValueError:
                    return v

            if SetOptionCommand.INTEGER_RE.match(v) is not None:
                #int ?
                try:
                    return int(v)
                except ValueError:
                    return v

            # string
            return v

        if len(args) == 2:
            option = args[0]
            value = convert_value(args[1])

        elif len(args) == 3:
            market_id = args[0]
            option = args[1]
            value = convert_value(args[2])

        if market_id:
            self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
                'market-id': market_id,
                'action': action,
                'option': option,
                'value': value
            })
        else:
            self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY_ALL, {
                'action': action,
                'option': option,
                'value': value
            })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            # instrument
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class SetFrozenQuantityCommand(Command):

    SUMMARY = "<market-id> to modify the frozen quantity per asset."

    def __init__(self, trader_service):
        super().__init__('set-frozen', 'SETFRZ')

        self._trader_service = trader_service

    def execute(self, args):
        if len(args) != 2:
            return False, "Missing parameters"

        action = "set-frozen"

        try:
            asset_name = args[0]
            quantity = float(args[1])

        except Exception:
            return False, "Invalid parameters"

        self._trader_service.command(Trader.COMMAND_TRADER_FROZE_ASSET_QUANTITY, {
            'asset': asset_name,
            'quantity': quantity,
            'action': action
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            # asset
            trader = self._trader_service.trader()
            if trader:
                return self.iterate(0, trader.assets_names(), args, tab_pos, direction)

        return args, 0


class LongCommand(Command):

    SUMMARY = "to manually create to a new trade in LONG direction"

    def __init__(self, strategy_service):
        super().__init__('long', 'L')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        # ie: ":long BTCUSDT L@8500 SL@8300 TP@9600 1.0"
        market_id = None

        # direction base on command name
        direction = 1
        method = 'market'
        limit_price = None
        trigger_price = None
        stop_loss = 0.0
        take_profit = 0.0
        stop_loss_price_mode = "price"
        take_profit_price_mode = "price"
        quantity_rate = 1.0
        timeframe = Instrument.TF_4HOUR
        entry_timeout = None
        leverage = None
        context = None

        if len(args) < 1:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            for value in args[1:]:
                if not value:
                    continue

                if value.startswith("L@") or value.startswith("l@"):
                    method = 'limit'
                    limit_price = float(value[2:])

                elif value.startswith("L+") or value.startswith("l+"):
                    dist = int(value[2:])

                    if dist < 1 or dist > 500:
                        return False, "Bid depth must be from 1 to 500"

                    method = 'best+%s' % dist

                elif value.startswith("L-") or value.startswith("l-"):
                    dist = int(value[2:])

                    if dist < 1 or dist > 500:
                        return False, "Ask depth must be from 1 to 500"

                    method = 'best-%s' % dist

                elif value.startswith("T@") or value.startswith("t@"):
                    method = 'trigger'
                    trigger_price = float(value[2:])

                elif value.startswith("SL@") or value.startswith("sl@"):
                    stop_loss = float(value[3:])
                elif value.startswith("SL%") or value.startswith("sl%"):
                    stop_loss = float(value[3:])
                    stop_loss_price_mode = "percent"
                elif value.startswith("SL!") or value.startswith("sl!"):
                    stop_loss = float(value[3:])
                    stop_loss_price_mode = "pip"

                elif value.startswith("TP@") or value.startswith("tp@"):
                    take_profit = float(value[3:])
                elif value.startswith("TP%") or value.startswith("tp%"):
                    take_profit = float(value[3:])
                    take_profit_price_mode = "percent"
                elif value.startswith("TP!") or value.startswith("tp!"):
                    take_profit = float(value[3:])
                    take_profit_price_mode = "pip"

                elif value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])

                elif value.startswith("*"):
                    quantity_rate = float(value[1:])

                elif value.endswith("%"):
                    quantity_rate = float(value[:-1]) * 0.01

                elif value.startswith("/"):
                    entry_timeout = timeframe_from_str(value[1:])

                elif value.startswith("x"):
                    leverage = float(value[1:])

                elif value.startswith("-"):
                    context = value[1:]

        except Exception:
            return False, "Invalid parameters"

        if limit_price and stop_loss and stop_loss_price_mode == "price" and stop_loss > limit_price:
            return False, "Stop-loss must be lesser than limit price"

        if limit_price and take_profit and take_profit_price_mode == "price" and take_profit < limit_price:
            return False, "Take-profit must be greater than limit price"

        if quantity_rate <= 0.0:
            return False, "Quantity must be non empty"

        self._strategy_service.command(Strategy.COMMAND_TRADE_ENTRY, {
            'market-id': market_id,
            'direction': direction,
            'limit-price': limit_price,
            'trigger-price': trigger_price,
            'method': method,
            'quantity-rate': quantity_rate,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'stop-loss-price-mode': stop_loss_price_mode,
            'take-profit-price-mode': take_profit_price_mode,
            'timeframe': timeframe,
            'entry-timeout': entry_timeout,
            'leverage': leverage,
            'context': context
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class ShortCommand(Command):

    SUMMARY = "to manually create to a new trade in SHORT direction"
   
    def __init__(self, strategy_service):
        super().__init__('short', 'S')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        # ie: ":long BTCUSDT L@8500 SL@8300 TP@9600 1.0"
        market_id = None

        # direction base on command name
        direction = -1
        method = 'market'
        limit_price = None
        trigger_price = None
        stop_loss = 0.0
        take_profit = 0.0
        stop_loss_price_mode = "price"
        take_profit_price_mode = "price"
        quantity_rate = 1.0
        timeframe = Instrument.TF_4HOUR
        entry_timeout = None
        leverage = None
        context = None

        if len(args) < 1:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            for value in args[1:]:
                if not value:
                    continue

                if value.startswith("L@") or value.startswith("l@"):
                    method = 'limit'
                    limit_price = float(value[2:])

                elif value.startswith("L+") or value.startswith("l+"):
                    dist = int(value[2:])

                    if dist < 1 or dist > 500:
                        return False, "Ask depth must be from 1 to 500"

                    method = 'best+%s' % dist

                elif value.startswith("L-") or value.startswith("l-"):
                    dist = int(value[2:])

                    if dist < 1 or dist > 500:
                        return False, "Bid depth must be from 1 to 500"

                    method = 'best-%s' % dist

                elif value.startswith("T@") or value.startswith("t@"):
                    method = 'trigger'
                    trigger_price = float(value[2:])

                elif value.startswith("SL@") or value.startswith("sl@"):
                    stop_loss = float(value[3:])
                elif value.startswith("SL%") or value.startswith("sl%"):
                    stop_loss = float(value[3:])
                    stop_loss_price_mode = "percent"
                elif value.startswith("SL!") or value.startswith("sl!"):
                    stop_loss = float(value[3:])
                    stop_loss_price_mode = "pip"

                elif value.startswith("TP@") or value.startswith("tp@"):
                    take_profit = float(value[3:])
                elif value.startswith("TP%") or value.startswith("tp%"):
                    take_profit = float(value[3:])
                    take_profit_price_mode = "percent"
                elif value.startswith("TP!") or value.startswith("tp!"):
                    take_profit = float(value[3:])
                    take_profit_price_mode = "pip"

                elif value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])

                elif value.startswith("*"):
                    quantity_rate = float(value[1:])

                elif value.endswith("%"):
                    quantity_rate = float(value[:-1]) * 0.01

                elif value.startswith("/"):
                    entry_timeout = timeframe_from_str(value[1:])

                elif value.startswith("x"):
                    leverage = float(value[1:])

                elif value.startswith("-"):
                    context = value[1:]

        except Exception:
            return False, "Invalid parameters"

        if limit_price and stop_loss and stop_loss_price_mode == "price"  and stop_loss < limit_price:
            return False, "Stop-loss must be greater than limit price"

        if limit_price and take_profit and take_profit_price_mode == "price" and take_profit > limit_price:
            return False, "Take-profit must be lesser than limit price"

        if quantity_rate <= 0.0:
            return False, "Quantity must be non empty"

        self._strategy_service.command(Strategy.COMMAND_TRADE_ENTRY, {
            'market-id': market_id,
            'direction': direction,
            'limit-price': limit_price,
            'trigger-price': trigger_price,
            'method': method,
            'quantity-rate': quantity_rate,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'stop-loss-price-mode': stop_loss_price_mode,
            'take-profit-price-mode': take_profit_price_mode,
            'timeframe': timeframe,
            'entry-timeout': entry_timeout,
            'leverage': leverage,
            'context': context
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class CloseCommand(Command):

    SUMMARY = "to manually close a managed trade at market or limit"

    def __init__(self, strategy_service):
        super().__init__('close', 'C')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        market_id = None
        trade_id = None
        action = "close"

        # ie ":close EURUSD 5"
        if len(args) != 2:
            return False, "Missing parameters"

        try:
            market_id = args[0]
            trade_id = int(args[1])

        except Exception:
            return False, "Invalid parameters"

        self._strategy_service.command(Strategy.COMMAND_TRADE_EXIT, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class CleanCommand(Command):

    SUMMARY = "to manually force to remove a managed trade and all its related orders without reducing its remaining quantity"

    def __init__(self, strategy_service):
        super().__init__('clean-trade', 'CT')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        market_id = None
        trade_id = None
        action = "clean"

        # ie ":clean XRPUSDT 5"
        if len(args) != 2:
            return False, "Missing parameters"

        try:
            market_id = args[0]
            trade_id = int(args[1])

        except Exception:
            return False, "Invalid parameters"

        self._strategy_service.command(Strategy.COMMAND_TRADE_CLEAN, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class DynamicStopLossOperationCommand(Command):
    
    SUMMARY = "to manually add a dynamic-stop-loss operation on a trade"
    HELP = (
        "param1: market-id",
        "param2: trade-id",
        "param3: trigger-price",
        "param4: stop-loss-price"
    )

    def __init__(self, strategy_service):
        super().__init__('dynamic-stop-loss', 'DSL')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        market_id = None
        trade_id = None

        action = "add-op"
        op = "dynamic-stop-loss"

        trigger = 0.0
        stop_loss = 0.0

        # ie ":DSL EURUSD 4 1.12 1.15"
        if len(args) != 4:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            trade_id = int(args[1])

            trigger = float(args[2])
            stop_loss = float(args[3])
        except Exception:
            return False, "Invalid parameters"

        self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'operation': op,
            'trigger': trigger,
            'stop-loss': stop_loss
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class RemoveOperationCommand(Command):

    SUMMARY = "to manually remove an operation from a trade"
    HELP = (
        "param1: market-id",
        "param2: trade-id"
    )

    def __init__(self, strategy_service):
        super().__init__('del', 'D')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        market_id = None
        trade_id = None

        action = 'del-op'
        operation_id = None        

        # ie ":SL EURUSD 1 5"
        if len(args) < 3:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            trade_id = int(args[1])
            operation_id = int(args[2])   
        except Exception:
            return False, "Invalid parameters"

        self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'operation-id': operation_id
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class ModifyStopLossCommand(Command):

    SUMMARY = "to manually modify the stop-loss of a trade"
    HELP = (
        "param1: market-id",
        "param2: trade-id",
        "param3: stop-loss-price",
        "param4 (optionnal) : add force to create an order or modify the position, not only have a local value",
    )
   
    def __init__(self, strategy_service):
        super().__init__('stop-loss', 'SL')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        market_id = None
        trade_id = None

        action = 'stop-loss'
        method = 'price'
        stop_loss = 0.0
        force = False

        # ie ":SL EURUSD 1 1.10"
        if len(args) < 3:
            return False, "Missing parameters"

        try:
            market_id = args[0]
            trade_id = int(args[1])

            if args[2].startswith('+'):
                # plus relative price or %
                if args[2].endswith('%'):
                    method = 'price-add-percent'
                    stop_loss = float(args[2][1:-1])
                else:
                    method = 'price-add-delta'
                    stop_loss = float(args[2][1:])

            elif args[2].startswith('-'):
                # minus relative price or %
                if args[2].endswith('%'):
                    method = 'price-minus-percent'
                    stop_loss = float(args[2][1:-1])
                else:
                    method = 'price-minus-delta'
                    stop_loss = float(args[2][1:])

            elif args[2].startswith("EP+") or args[2].startswith("ep+"):
                # entry-price plus delta
                if args[2].endswith('%'):
                    method = 'breakeven-plus-percent'
                    stop_loss = float(args[2][3:-1])
                else:
                    method = 'breakeven-plus-delta'
                    stop_loss = float(args[2][3:])

            elif args[2].startswith("EP-") or args[2].startswith("ep-"):
                # entry-price minus delta
                if args[2].endswith('%'):
                    method = 'breakeven-minus-percent'
                    stop_loss = float(args[2][3:-1])
                else:
                    method = 'breakeven-minus-delta'
                    stop_loss = float(args[2][3:])

            else:
                stop_loss = float(args[2])

            if len(args) > 3:
                # create an order or modify the position, else use default
                force = str(args[3]) == "force"

        except Exception:
            return False, "Invalid parameters"

        self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'method': method,
            'stop-loss': stop_loss,
            'force': force
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class ModifyTakeProfitCommand(Command):

    SUMMARY = "to manually modify the take-profit of a trade"
    HELP = (
        "param1: market-id",
        "param2: trade-id",
        "param3: take-profit-price",
        "param4 (optionnal) : add force to create an order or modify the position, not only have a local value",
    )

    def __init__(self, strategy_service):
        super().__init__('take-profit', 'TP')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        market_id = None
        trade_id = None

        action = 'take-profit'
        method = 'price'
        take_profit = 0.0
        force = False

        # ie ":TP EURUSD 1 1.15"
        if len(args) < 3:
            return False, "Missing parameters"

        try:
            market_id = args[0]
            trade_id = int(args[1])

            if args[2].startswith('+'):
                # plus relative price or %
                if args[2].endswith('%'):
                    method = 'price-add-percent'
                    take_profit = float(args[2][1:-1])
                else:
                    method = 'price-add-delta'
                    take_profit = float(args[2][1:])

            elif args[2].startswith('-'):
                # minus relative price or %
                if args[2].endswith('%'):
                    method = 'price-minus-percent'
                    take_profit = float(args[2][1:-1])
                else:
                    method = 'price-minus-delta'
                    take_profit = float(args[2][1:])

            elif args[2].startswith("EP+") or args[2].startswith("ep+"):
                # entry-price plus delta
                if args[2].endswith('%'):
                    method = 'breakeven-plus-percent'
                    take_profit = float(args[2][3:-1])
                else:
                    method = 'breakeven-plus-delta'
                    take_profit = float(args[2][3:])

            elif args[2].startswith("EP-") or args[2].startswith("ep-"):
                # entry-price minus delta
                if args[2].endswith('%'):
                    method = 'breakeven-minus-percent'
                    take_profit = float(args[2][3:-1])
                else:
                    method = 'breakeven-minus-delta'
                    take_profit = float(args[2][3:])

            else:
                take_profit = float(args[2])

            if len(args) > 3:
                # create an order or modify the position, else use default
                force = str(args[3]) == "force"

        except Exception:
            return False, "Invalid parameters"

        self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'method': method,
            'take-profit': take_profit,
            'force': force
        })

        return True, []
    
    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class TradeInfoCommand(Command):

    SUMMARY = "to get operation info of a specific trade"
    HELP = (
        "param1: market-id",
        "param2: trade-id"
    )

    def __init__(self, strategy_service):
        super().__init__('trade', 'T')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        market_id = None
        trade_id = None

        if len(args) >= 1:
            try:
                market_id = args[0]

                if len(args) >= 2:
                    trade_id = int(args[1])
                else:
                    trade_id = -1

            except Exception:
                return False, "Invalid parameters"

            self._strategy_service.command(Strategy.COMMAND_TRADE_INFO, {
                'market-id': market_id,
                'trade-id': trade_id
            })

            return True, []
        else:
            return False, "Missing or invalid parameters"

        return False, None

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class AssignCommand(Command):

    SUMMARY = "to manually assign a quantity of asset to a new trade in LONG direction"

    def __init__(self, strategy_service):
        super().__init__('assign', 'AS')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        # ie: ":assign BTCUSDT EP@8500 SL@8300 TP@9600 0.521"
        market_id = None

        # direction base on command name
        direction = 1
        entry_price = None
        stop_loss = 0.0
        take_profit = 0.0
        quantity = 0.0
        timeframe = Instrument.TF_4HOUR
        context = None

        if len(args) < 2:
            return False, "Missing parameters. Need at least entry price and quantiy"

        try:
            market_id = args[0]

            for value in args[1:]:
                if not value:
                    continue

                if value == 'L' or value == 'long':
                    direction = 1
                elif value == 'S' or value == 'short':
                    direction = -1
                elif value.startswith("EP@"):
                    entry_price = float(value[3:])
                elif value.startswith("SL@"):
                    stop_loss = float(value[3:])
                elif value.startswith("TP@"):
                    take_profit = float(value[3:])
                elif value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])
                elif value.startswith("-"):
                    context = value[1:]
                else:
                    quantity = float(value)

        except Exception:
            return False, "Invalid parameters"

        if entry_price <= 0.0:
            return False, "Entry price must be specified"

        if stop_loss:
            if direction > 0 and stop_loss >= entry_price:
                return False, "Stop-loss must be lesser than entry price"
            elif direction < 0 and stop_loss <= entry_price:
                return False, "Stop-loss must be greater than entry price"

        if take_profit:
            if direction > 0 and take_profit <= entry_price:
                return False, "Take-profit must be greater than entry price"
            elif direction < 0 and take_profit >= entry_price:
                return False, "Take-profit must be lesser than entry price"

        if quantity <= 0.0:
            return False, "Quantity must be specified"

        self._strategy_service.command(Strategy.COMMAND_TRADE_ASSIGN, {
            'market-id': market_id,
            'direction': direction,
            'entry-price': entry_price,
            'quantity': quantity,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'timeframe': timeframe,
            'context': context
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

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

    SUMMARY = "to change the traded quantity and scale factor per any or specific market"
    
    def __init__(self, strategy_service):
        super().__init__('set-quantity', 'SETQTY')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        # ie: ":setquantity BTCUSDT 1000 1"
        action = "set-quantity"
        market_id = None
        quantity = 0.0
        max_factor = 1

        if len(args) < 1:
            return False, "Missing parameters"

        is_float = True

        try:
            float(args[0])
        except ValueError:
            is_float = False

        if is_float:
            try:
                quantity = float(args[0])
            except ValueError:
                return False, "Invalid quantity format"

            if len(args) == 2:
                try:
                    max_factor = int(args[1])
                except ValueError:
                    return False, "Invalid scale factor value"
        else:
            market_id = args[0]

            try:
                quantity = float(args[1])
            except ValueError:
                return False, "Invalid quantity format"

            if len(args) == 3:
                try:
                    max_factor = int(args[2])
                except ValueError:
                    return False, "Invalid scale factor value"

        if quantity <= 0.0:
            return False, "Invalid quantity, must be greater than zero"

        if max_factor < 1:
            return False, "Invalid max factor, must be greater than zero"

        if market_id:
            self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
                'market-id': market_id,
                'action': action,
                'quantity': quantity,
                'max-factor': max_factor
            })
        else:
            self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY_ALL, {
                'action': action,
                'quantity': quantity,
                'max-factor': max_factor
            })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            if len(args) == 1:
                is_float = True

                try:
                    float(args[0])
                except ValueError:
                    is_float = False

                if is_float:
                    return args, 0

            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class CloseAllTradeCommand(Command):

    SUMMARY = "to close any current position and trade (and a specified market or any)"
    
    def __init__(self, strategy_service):
        super().__init__('!closeall', '!CA')

        self._strategy_service = strategy_service

    def execute(self, args):
        # ie: ":closeall BTCUSDT"
        market_id = None

        if len(args) == 1:
            market_id = args[0]

        self._strategy_service.command(Strategy.COMMAND_TRADE_EXIT_ALL, {
            'market-id': market_id,
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class SellAllAssetCommand(Command):

    SUMMARY = "to sell at market, immediately any quantity availables of free assets (for a specified market or any)"
    
    def __init__(self, trader_service):
        super().__init__('!sellall', '!SA')

        self._trader_service = trader_service

    def execute(self, args):
        # ie: ":sellall BTCUSDT"
        market_id = None

        if len(args) == 1:
            market_id = args[1]

        self._trader_service.command(Trader.COMMAND_SELL_ALL_ASSET, {
            'market-id': market_id,
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            trader = self._trader_service.trader()
            if trader:
                return self.iterate(0, trader.symbols_ids(), args, tab_pos, direction)

        return args, 0


class CancelAllOrderCommand(Command):

    SUMMARY = "to cancel any orders, immediately (for a specified market or any)"
    
    def __init__(self, trader_service):
        super().__init__('!rmallorder', '!CAO')

        self._trader_service = trader_service

    def execute(self, args):
        # ie: ":sellall BTCUSDT"
        market_id = None

        if len(args) == 1:
            market_id = args[1]

        self._trader_service.command(Trader.COMMAND_CANCEL_ALL_ORDER, {
            'market-id': market_id,
        })

        return True, []

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            trader = self._trader_service.trader()
            if trader:
                return self.iterate(0, trader.symbols_ids(), args, tab_pos, direction)

        return args, 0


class ReconnectCommand(Command):

    SUMMARY = "to force to reconnect"
    
    def __init__(self, watcher_service):
        super().__init__('reconnect', 'RECON')

        self._watcher_service = watcher_service

    def execute(self, args):
        # will force to try to reconnect
        if len(args) == 1:
            self._watcher_service.reconnect(args[0])
            return True, "Force reconnect for watcher %s" % args[0]

        self._watcher_service.reconnect()
        return True, "Force reconnect for any watchers"

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            watchers_ids = self._watcher_service.watchers_ids()
            return self.iterate(0, watchers_ids, args, tab_pos, direction)

        return args, 0


def register_trading_commands(commands_handler, watcher_service, trader_service, strategy_service, monitor_service, notifier_service):
    #
    # global
    #

    commands_handler.register(PlayCommand(strategy_service, notifier_service))
    commands_handler.register(PauseCommand(strategy_service, notifier_service))
    commands_handler.register(InfoCommand(strategy_service, notifier_service))
    commands_handler.register(UserSaveCommand(strategy_service))
    commands_handler.register(SetQuantityCommand(strategy_service))
    commands_handler.register(SetAffinityCommand(strategy_service))
    commands_handler.register(SetOptionCommand(strategy_service))
    commands_handler.register(SetFrozenQuantityCommand(trader_service))

    commands_handler.register(ReconnectCommand(watcher_service))

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

    commands_handler.register(CleanCommand(strategy_service))
    commands_handler.register(TradeInfoCommand(strategy_service))
    commands_handler.register(RemoveOperationCommand(strategy_service))
    commands_handler.register(DynamicStopLossOperationCommand(strategy_service))

    #
    # multi-trades operations
    #

    commands_handler.register(CloseAllTradeCommand(strategy_service))
    commands_handler.register(SellAllAssetCommand(trader_service))
    commands_handler.register(CancelAllOrderCommand(trader_service))
    # commands_handler.register(CloseAllPositionCommand(trader_service))
    # commands_handler.register(ClosePositionCommand(trader_service))
