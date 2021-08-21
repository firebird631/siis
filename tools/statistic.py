# @date 2021-05-03
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Statistic tools

import sys
import traceback

from datetime import datetime, timedelta

from tools.tool import Tool
from config import utils

from common.utils import timeframe_from_str, UTC

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.tools.statistic')
error_logger = logging.getLogger('siis.tools.error.statistic')


class Statistic(Tool):
    """
    Make a connection and synchronize the market data in local DB.
    """ 

    @classmethod
    def alias(cls):
        return "stats"

    @classmethod
    def help(cls):
        return ("Process a statistic datasheet for a period.",
                "Specify --broker, --strategy, --from, --to, --timeframe.",
                "Optional --market, --filename=<filename.csv|xlsx>.")

    @classmethod
    def detailed_help(cls):
        return tuple()

    @classmethod
    def need_identity(cls):
        return True

    def __init__(self, options):
        super().__init__("statistic", options)

        self._identity = options.get('identity')
        self._identities_config = utils.identities(options.get('config-path'))

        self._profile = options.get('profile', 'default')

        self._profile_config = utils.load_config(options, "profiles/%s" % self._profile)

        self._from_date = options.get('from')  # UTC tz
        self._to_date = options.get('to')  # UTC tz

        self._total_perf = 0.0
        self._total_perf_pct = 0.0

        self._worst_upnl = 0.0
        self._best_upnl = 0.0

        self._avg_pnl = 0.0

        self._currency = "USD"
        self._currency_precision = 2

        self._report = []
        self._intervals = {}

    def identity(self, name):
        return self._identities_config.get(name, {}).get(self._identity)

    def check_options(self, options):
        if not options.get('profile'):
            logger.error("Missing profile")
            return False

        if not options.get('from') or not options.get('to') or not options.get('timeframe'):
            logger.error("Options from, to and timeframe must be defined")
            return False

        timeframe = timeframe_from_str(options.get('timeframe'))

        if timeframe <= 0:
            logger.error("Timeframe cannot refers to an empty period")

        if options.get('filename'):
            if options['filename'][-4:] == '.csv':
                logger.error("Base filename only must be specified")
                return False

        return True

    def init(self, options):
        # database manager
        Database.create(options)
        Database.inst().setup(options)

        return True

    def run(self, options):
        strategy = self._profile_config.get('strategy', {})

        if not strategy:
            logger.error("Missing strategy")
            return False

        trader = self._profile_config.get('trader', {})

        if not trader:
            logger.error("Missing trader")
            return False

        trader_id = trader.get('name')

        if not trader_id:
            logger.error("Missing trader name")
            return False

        identity = self.identity(trader_id)

        account_id = identity.get('account-id')
        strategy_id = strategy.get('id', None)
        strategy_name = strategy.get('name', None)

        self._currency = trader.get('preference', {}).get('currency', "USD")

        if not strategy_name:
            logger.error("Missing strategy name")
            return False

        if not strategy_id:
            logger.error("Missing strategy identifier")
            return False

        timeframe = timeframe_from_str(options.get('timeframe'))

        from_date = self._from_date.replace(timezone=UTC())
        to_date = self._to_date.replace(timezone=UTC())

        market_id = None

        if 'market' in options:
            market_id = options['market'].split(',')

        user_closed_trades = Database.inst().get_user_closed_trades(trader_id, account_id, strategy_id,
                                                                    from_date, to_date, market_id)

        if user_closed_trades is None:
            logger.error("Unable to retrieve some historical user trades")
            return False

        # generate intervals
        t = from_date
        while t <= to_date:
            self._intervals[t.timestamp()] = (
                t.strftime('%Y-%m-%dT%H:%M:%SZ'),
                (t + timedelta(seconds=timeframe-1.0)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                0.0,  # price
                0.0,  # percent
                self._currency)

            t += timedelta(seconds=timeframe)

        for trade in user_closed_trades:
            # found the related interval for the last exit timestamp
            interval = self.find_interval(trade)

            # add each trade and insert it into its interval
            self.add_trade(trade, interval)

        # from_interval = from_date.timestamp()
        # to_interval = from_interval + timeframe

        # for trade in user_closed_trades:
        #     if trade[1] >= to_interval:
        #         # next interval of aggregation
        #         from_interval = to_interval
        #         to_interval = from_interval + timeframe
        #
        #         self.finalize_aggregate(from_interval, to_interval)
        #
        #     self.add_trade(trade)

        # last aggregate
        # self.finalize_aggregate(from_interval, to_interval)

        if options.get('filename'):
            self.write_report(options.get('filename'))
        else:
            self.write_log()

        formated_total_perf = "{:0.0{}f}{}".format(self._total_perf, self._currency_precision, self._currency)

        print("Total performance : %.2f%% %s" % (self._total_perf_pct, formated_total_perf))

        return True

    def find_interval(self, trade):
        if not trade:
            return None

        if (trade[2] and 'stats' in trade[2] and 'last-realized-exit-datetime' in trade[2]['stats'] and
                trade[2]['stats']['last-realized-exit-datetime']):
            trade_exit_ts = datetime.strptime(trade[2]['stats']['last-realized-exit-datetime'],
                                              '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=UTC()).timestamp()
        else:
            trade_exit_ts = trade[1]

        for ts, agg in self._intervals.items():
            if agg[0] >= trade_exit_ts <= agg[1]:
                return agg

        return None

    def add_trade(self, trade, interval):
        data = trade[2]
        stats = data['stats']

        rpnl_pct = float(data['profit-loss-pct'])

        #
        # global
        #

        fees = stats['entry-fees'] + stats['exit-fees']

        # self._total_perf += stats['profit-loss']
        self._total_perf_pct += rpnl_pct

        entry_size = float(data['filled-entry-qty']) * float(data['avg-entry-price'])
        exit_size = float(data['filled-exit-qty']) * float(data['avg-exit-price'])

        realized_profit = exit_size - entry_size - fees
        self._total_perf += realized_profit

        #
        # interval
        #

        if interval:
            interval[3] += realized_profit
            interval[2] += rpnl_pct

        #
        # record
        #

        # 'trade': self.trade_type_to_str(),
        # 'id': self.id,
        # 'timestamp': timestamp,
        # 'market-id': strategy_trader.instrument.market_id,
        # 'symbol': strategy_trader.instrument.symbol,
        # 'timeframe': timeframe_to_str(self._timeframe),
        # 'is-user-trade': self._user_trade,
        # 'label': self._label,
        # 'direction': self.direction_to_str(),
        # 'state': self.state_to_str(),
        # 'order-price': strategy_trader.instrument.format_price(self.op),
        # 'order-qty': strategy_trader.instrument.format_quantity(self.oq),
        # 'stop-loss-price': strategy_trader.instrument.format_price(self.sl),
        # 'take-profit-price': strategy_trader.instrument.format_price(self.tp),
        # 'avg-entry-price': strategy_trader.instrument.format_price(self.aep),
        # 'avg-exit-price': strategy_trader.instrument.format_price(self.axp),
        # 'entry-open-time': self.dump_timestamp(self.eot),
        # 'exit-open-time': self.dump_timestamp(self.xot),
        # 'filled-entry-qty': strategy_trader.instrument.format_quantity(self.e),
        # 'filled-exit-qty': strategy_trader.instrument.format_quantity(self.x),
        # 'profit-loss-pct': round((self.pl - self.entry_fees_rate() - self.exit_fees_rate()) * 100.0, 2),  # minus fees
        # 'num-exit-trades': len(self.exit_trades),
        # 'stats': {
        #     'best-price': strategy_trader.instrument.format_price(self._stats['best-price']),
        #     'best-datetime': self.dump_timestamp(self._stats['best-timestamp']),
        #     'worst-price': strategy_trader.instrument.format_price(self._stats['worst-price']),
        #     'worst-datetime': self.dump_timestamp(self._stats['worst-timestamp']),
        #     'entry-order-type': order_type_to_str(self._stats['entry-order-type']),
        #     'first-realized-entry-datetime': self.dump_timestamp(self._stats['first-realized-entry-timestamp']),
        #     'first-realized-exit-datetime': self.dump_timestamp(self._stats['first-realized-exit-timestamp']),
        #     'last-realized-entry-datetime': self.dump_timestamp(self._stats['last-realized-entry-timestamp']),
        #     'last-realized-exit-datetime': self.dump_timestamp(self._stats['last-realized-exit-timestamp']),
        #     'profit-loss-currency': self._stats['profit-loss-currency'],
        #     'profit-loss': self._stats['unrealized-profit-loss'],  # @todo
        #     'entry-fees': self._stats['entry-fees'],
        #     'exit-fees': self._stats['exit-fees'],
        #     'fees-pct': round((self.entry_fees_rate() + self.exit_fees_rate()) * 100.0, 2),
        #     'exit-reason': StrategyTrade.reason_to_str(self._stats['exit-reason']),
        # }

        # 'trade' type : 'asset', 'margin', 'ind-margin', 'position', 'undefined'

        row = (
            data['symbol'],
            data['id'],
            data['trade'],
            data['direction'],
            data['avg-entry-price'],
            data['filled-entry-qty'],
            data['stats']['first-realized-entry-datetime'] or "",
            data['avg-exit-price'],
            data['filled-exit-qty'],
            data['stats']['last-realized-exit-datetime'] or ""
        )

        self._report.append(row)

    def finalize_aggregate(self, from_interval, to_interval):
        # @todo insert empty interval

        # compute last interval
        interval = (
            datetime.fromtimestamp(from_interval, tz=UTC()).strftime('%Y-%m-%dT%H:%M:%SZ'),
            datetime.fromtimestamp(to_interval-1.0, tz=UTC()).strftime('%Y-%m-%dT%H:%M:%SZ'),
            self._interval_perf_pct,
            self._interval_perf,
            self._currency
        )

        self._intervals[from_interval] = interval

        self._interval_perf = 0.0
        self._interval_perf_pct = 0.0

    def write_report(self, filename):
        if not filename:
            return

        #
        # perf
        #

        try:
            f = open(filename + "_perf.csv", 'wt')

            for r in self._report:
                row = (r[0], "%i" % r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9])
                f.write('\t'.join(row) + '\n')

            f.close()
            f = None

        except Exception as e:
            logger.error(repr(e))

        #
        # interval perf
        #
        
        try:
            f = open(filename + "_intervals.csv", 'wt')

            # header
            row = ("from", "to", "realized_pnl_pct", "realized_pnl", "currency")
            f.write('\t'.join(row) + '\n')

            for t, r in self._intervals.items():
                formatted_price = "{:0.0{}f}".format(r[3], self._currency_precision)

                row = (r[0], r[1], "%.2f" % r[2], formatted_price, self._currency)
                f.write('\t'.join(row) + '\n')

            f.close()
            f = None

        except Exception as e:
            logger.error(repr(e))

    def write_log(self):
        for r in self._report:
            row = (r[0], "%i" % r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9])
            print('\t'.join(row))

        for t, r in self._intervals.items():
            formatted_price = "{:0.0{}f}{}".format(r[3], self._currency_precision, self._currency)

            row = (r[0], r[1], "%.2f%%" % r[2], formatted_price)
            print('\t'.join(row))

    def terminate(self, options):
        Database.terminate()

        return True

    def forced_interrupt(self, options):
        return True


tool = Statistic
