# @date 2020-03-07
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# terminal alert commands and registration

import time

from datetime import datetime

from terminal.command import Command
from strategy.strategy import Strategy
from trader.trader import Trader

from terminal.terminal import Terminal
from common.utils import timeframe_from_str

from instrument.instrument import Instrument


class PriceCrossAlertCommand(Command):

    SUMMARY = "to manually add a price-cross alert on a strategy"
    HELP = (":price-cross-alert <appliance-id> <market-id> <price>",
            "optional parameters:",
            "- C@<price> : cancelation price",
            "- @<timestamp|duration> : expiry",
            "- '<timeframe> : timeframe")
    
    def __init__(self, strategy_service):
        super().__init__('price-cross-alert', 'pca')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        appliance = None
        market_id = None
        timeframe = -1

        action = "add-alert"
        reg = "price-cross"
        stage = 0
        direction = 0
        expiry = 0.0
        created = self._strategy_service.timestamp

        price = 0.0
        cancelation = 0.0

        # ie ":PCA _ EURUSD 1.12"
        if len(args) < 3:
            Terminal.inst().action("Missing parameters", view='status')
            return False

        try:
            appliance, market_id = args[0], args[1]

            price = float(args[2])

            for value in args[3:]:
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

        except Exception:
            Terminal.inst().action("Invalid parameters", view='status')
            return False

        self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
            'appliance': appliance,
            'market-id': market_id,
            'action': action,
            'region': reg,
            'created': created,
            'timeframe': timeframe,
            'expiry': expiry,
            'price': price,
            'cancelation': cancelation
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


def register_alert_commands(commands_handler, strategy_service):
    cmd = PriceCrossAlertCommand(strategy_service)
    commands_handler.register(cmd)
