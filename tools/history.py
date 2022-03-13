# @date 2021-05-16
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# History tools

import json

from tools.tool import Tool
from config import utils

from terminal.terminal import Terminal

from watcher.service import WatcherService

import logging
logger = logging.getLogger('siis.tools.history')
error_logger = logging.getLogger('siis.tools.error.history')

READ_DEBUG_CACHE = 0
WRITE_DEBUG_CACHE = 0


class History(Tool):
    """
    Make a connection and take the history of orders or position.
    """ 

    ORDERS_HEADER = (
        'id',
        'symbol',
        'market-id',
        'status',
        'ref-id',
        'direction',
        'type',
        'mode',
        'timestamp',
        'avg-price',
        'quantity',
        'cumulative-filled',
        'cumulative-commission-amount',
        'price',
        'stop-price',
        'time-in-force',
        'post-only',
        'close-only',
        'reduce-only',
        'stop-loss',
        'take-profit',
        'fully-filled',
        'trades'
    )

    @classmethod
    def alias(cls):
        return "hist"

    @classmethod
    def help(cls):
        return ("Process a checkout of the history of orders or position from a particular account and period.",
                "Specify --profile, --broker, --from, --to.",
                "Optional --market, --filename.")

    @classmethod
    def detailed_help(cls):
        return tuple()

    @classmethod
    def need_identity(cls):
        return True

    def __init__(self, options):
        super().__init__("history", options)

        self._watcher_service = None

        self._identity = options.get('identity')
        self._identities_config = utils.identities(options.get('config-path'))

        self._profile = options.get('profile', 'default')

        self._profile_config = utils.load_config(options, "profiles/%s" % self._profile)

    def check_options(self, options):
        if not options.get('from') or not options.get('to'):
            logger.error("Options from, and to must be defined")
            return False

        if not options.get('broker'):
            logger.error("Options broker must be defined")
            return False

        if options.get('filename'):
            if options['filename'][-4:] == '.csv':
                logger.error("Base filename only must be specified")
                return False

        return True

    def init(self, options):
        Terminal.inst().info("Starting watcher's service...")
        self._watcher_service = WatcherService(None, options)

        return True

    def run(self, options):
        strategy = self._profile_config.get('strategy', {})

        if not strategy:
            logger.error("Missing strategy")
            return False

        watchers = self._profile_config.get('watchers', {})

        if not watchers or options['broker'] not in watchers:
            logger.error("Missing watcher")
            return False

        watcher_id = options['broker']

        if not watcher_id:
            logger.error("Missing watcher name")
            return False

        markets = options['market'].split(',') if options.get('market') else None

        fetcher = self._watcher_service.create_fetcher(options, options['broker'])
        if fetcher:           
            fetcher.connect()

            closed_orders = []
            open_orders = []

            try:
                if READ_DEBUG_CACHE:
                    with open('c.tmp', 'rt') as f:
                        closed_orders = json.loads(f.read())
                else:
                    closed_orders = fetcher.fetch_closed_orders(options.get('from'), options.get('to'))
                    if WRITE_DEBUG_CACHE:
                        with open('c.tmp', 'wt') as f:
                            f.write(json.dumps(closed_orders))
            except Exception as e:
                error_logger.error("fetch_closed_orders : " + str(e))

            try:
                if READ_DEBUG_CACHE:
                    with open('o.tmp', 'rt') as f:
                        open_orders = json.loads(f.read())
                else:
                    open_orders = fetcher.fetch_open_orders()
                    if WRITE_DEBUG_CACHE:
                        with open('o.tmp', 'wt') as f:
                            f.write(json.dumps(open_orders))
            except Exception as e:
                error_logger.error("fetch_open_oders : " + str(e))

            # filter orders
            if markets:
                tmp = closed_orders
                closed_orders = []

                for o in tmp:
                    if o['market-id'] in markets:
                        closed_orders.append(o)

                tmp = open_orders
                open_orders = []

                for o in tmp:
                    if o['market-id'] in markets:
                        open_orders.append(o)

            # keep only close orders with cumulative filled greater than 0
            tmp = closed_orders
            closed_orders = []
            for o in tmp:
                if float(o['cumulative-filled']) > 0:
                    closed_orders.append(o)

            # keep only open orders opened before to_date
            tmp = open_orders
            open_orders = []
            filtered_open_orders = []
            from_date = options.get('from').strftime('%Y-%m-%dT%H:%M:%SZ')
            to_date = options.get('to').strftime('%Y-%m-%dT%H:%M:%SZ')
            for o in tmp:
                if o['timestamp'] >= from_date and o['timestamp'] <= to_date:
                    open_orders.append(o)
                else:
                    filtered_open_orders.append(o)

            if options.get('filename'):
                self.export_to_csv(closed_orders, open_orders, options['filename'])
            else:
                self.display(closed_orders, open_orders)

            fetcher.disconnect()

            paired, unpaired = self.detect_unmanaged(closed_orders, open_orders, filtered_open_orders)
            print(len(paired), len(unpaired), len(open_orders))

            if options.get('filename'):
                self.export_unpaired_orders_to_csv(unpaired, options['filename'])
            else:
                self.display_unpaired_orders(unpaired)

        return True

    def export_to_csv(self, closed_orders, open_orders, filename):
        # closed orders
        try:
            f = open(filename + "_closed.csv", 'wt')

            f.write('\t'.join(History.ORDERS_HEADER) + '\n')

            for o in closed_orders:
                row = [str(o[n]) for n in History.ORDERS_HEADER]
                f.write('\t'.join(row) + '\n')

            f.close()
            f = None

        except Exception as e:
            logger.error(repr(e))

        # open orders
        try:
            f = open(filename + "_open.csv", 'wt')

            f.write('\t'.join(History.ORDERS_HEADER) + '\n')

            for o in open_orders:
                row = [str(o[n]) for n in History.ORDERS_HEADER]
                f.write('\t'.join(row) + '\n')

            f.close()
            f = None

        except Exception as e:
            logger.error(repr(e))

    def display(self, closed_orders, open_orders):
        print("> Closed orders :")
        print('\t'.join(History.ORDERS_HEADER) + '\n')

        for o in closed_orders:
            # format to display or to CSV
            row = [str(o[n]) for n in History.ORDERS_HEADER]
            print('\t'.join(row))

        print("> Open orders :")
        print('\t'.join(History.ORDERS_HEADER) + '\n')

        for o in open_orders:
            # format to display or to CSV
            row = [str(o[n]) for n in History.ORDERS_HEADER]
            print('\t'.join(row))

    def detect_unmanaged(self, closed_orders, open_orders, filtered_open_orders):
        paired = {}
        unpaired = []

        # for each entry order try to find the corresponding exit
        # make a first list with detect pairs of orders
        # and a second list with the remaining
        entries = []
        exits = []

        # distinct entry and exit order from closed orders
        for o in closed_orders:
            if o['mode'] == "spot":
                if o['direction'] == "buy":
                    entries.append(o)
                elif o['direction'] == "sell":
                    exits.append(o)

            elif o['mode'] == "margin":
                # @todo test
                if o['reduce-only'] == "false" or o['close-only'] == "false":
                    entries.append(o)
                elif o['direction'] == "true" or o['close-only'] == "true":
                    exits.append(o)

        # and from open orders
        for o in open_orders:
            if o['mode'] == "spot":
                # if o['direction'] == "buy":
                #     entries.append(o)
                if o['direction'] == "sell":
                    exits.append(o)

            elif o['mode'] == "margin":
                # @todo test
                # if o['reduce-only'] == "false" or o['close-only'] == "false":
                #     entries.append(o)
                if o['direction'] == "true" or o['close-only'] == "true":
                    exits.append(o)

        # and from filtered open orders only keep exits
        for o in filtered_open_orders:
            if o['mode'] == "spot":
                if o['direction'] == "sell":
                    exits.append(o)

            elif o['mode'] == "margin":
                # @todo test
                if o['direction'] == "true" or o['close-only'] == "true":
                    exits.append(o)

        # detection
        for e in entries:
            rm = None

            for x in exits:
                if e['market-id'] != x['market-id']:
                    continue

                if e['timestamp'] <= x['timestamp']:
                    continue

                diff = ((float(e['cumulative-filled']) - float(x['cumulative-filled'])) / float(e['cumulative-filled']))

                if diff < 0.0 or diff > 0.001:
                   continue

                print(e['cumulative-filled'], x['cumulative-filled'], x['market-id'])

                paired[e['id']] = x
                rm = x
                break

            if rm:
                exits.remove(rm)
            else:
                unpaired.append(e)

        return paired, unpaired

    def display_unpaired_orders(self, unpaired_orders):
        print("> Unpaired orders :")
        print('\t'.join(History.ORDERS_HEADER) + '\n')

        for o in unpaired_orders:
            # format to display or to CSV
            row = [str(o[n]) for n in History.ORDERS_HEADER]
            print('\t'.join(row))

    def export_unpaired_orders_to_csv(self, unpaired_orders, filename):
        # unpaired orders
        try:
            f = open(filename + "_unpaired.csv", 'wt')

            f.write('\t'.join(History.ORDERS_HEADER) + '\n')

            for o in unpaired_orders:
                row = [str(o[n]) for n in History.ORDERS_HEADER]
                f.write('\t'.join(row) + '\n')

            f.close()
            f = None

        except Exception as e:
            logger.error(repr(e))

    def terminate(self, options):
        self._watcher_service.terminate()

        return True

    def forced_interrupt(self, options):
        return True


tool = History
