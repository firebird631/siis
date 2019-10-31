# @date 2018-09-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Paper trader history logger.

import json
import time

from datetime import datetime

from trader.position import Position

import logging
logger = logging.getLogger('siis.trader.papertrader.history')


class PaperTraderHistoryEntry(object):
    """
    History entry when paper trading, but could be done by an external listener, eventually a webapp.

    @todo Report the duration of the trade.
    @todo Streamable and for any trader, and more uniform.
    @todo Or maybe remove because we can use reporting from strategy directly with more details.
    """

    def __init__(self, order, balance, margin_balance, gain_loss_pip=None, gain_loss_rate=None, gain_loss_currency=None, gain_loss_account_currency=None):
        self._uid = 0
        self._order = order
        self._balance = balance
        self._margin_balance = margin_balance
        # self._asset_balance = asset_balance

        self._gain_loss_pip = gain_loss_pip
        self._gain_loss_rate = gain_loss_rate
        self._gain_loss_currency = gain_loss_currency
        self._gain_loss_account_currency = gain_loss_account_currency

    def set_uid(self, uid):
        self._uid = uid

    @property
    def order(self):
        return self._order
    
    @property
    def balance(self):
        return self._balance

    @property
    def margin_balance(self):
        return self._margin_balance

    @property
    def gain_loss_pip(self):
        return self._gain_loss_pip

    @property
    def gain_loss_rate(self):
        return self._gain_loss_rate

    @property
    def gain_loss_currency(self):
        return self._gain_loss_currency

    @property
    def gain_loss_account_currency(self):
        return self._gain_loss_account_currency

    def report(self, currency):
        """
        Return a string report.
        """
        direction = "LONG" if self._order.direction == Position.LONG else "SHORT"
        at = datetime.fromtimestamp(self._order.transact_time).strftime('%Y-%m-%dT%H:%M:%S.%fZ') if self._order.transact_time else ""

        if self._gain_loss_pip is not None:
            return '\t'.join((str(self._uid), "EXIT", direction, self._order.symbol, str(self._order.quantity), at,
                str(self._gain_loss_pip), str(self._gain_loss_rate*100.0), str(self._gain_loss_currency), str(self._balance)))
        else:
            return '\t'.join((str(self._uid), "ENTER", direction, self._order.symbol, str(self._order.quantity), at, "0", "0", "0", str(self._balance)))


class PaperTraderHistory(object):
    """
    History when paper trading, but could be done by an external listener, eventually a webapp.
    @todo generate/call signal for order and position (create, update, delete, reject, cancel) but how to manage them because if strategy listen from watcher ?
    @todo distinct multiple position of single per instrument and hedging mode.
    @todo add signals emit for position opened/update/closed
    @todo execution of limit order on price not as now as market with limit price (but for now it works because of the strategy ask for the ofr price and small volume)
    @todo with limit order lock the qty of the asset
    @todo check available margin when creating margin order
    @todo Best/worst are made for margin on account currency, but need to be updated to work with asset
    """

    def __init__(self, trader):
        self._trader = trader
        self._history = []

        self._live_rate = {}  # live rate in percent per market
        self._create_time = datetime.now()

    def add(self, entry):
        if entry:
            self._history.append(entry)
            entry.set_uid(len(self._history))

            if entry.order.symbol not in self._live_rate:
                self._live_rate[entry.order.symbol] = [0, 0]

            if entry.gain_loss_rate:
                self._live_rate[entry.order.symbol][0] += entry.gain_loss_rate
                self._live_rate[entry.order.symbol][1] += entry.gain_loss_currency

    def log_report(self):
        """
        Report to a log file into the report path.
        """
        currency = self._trader.account.currency

        # stats, and write
        worst_loss = 0
        best_profit = 0

        winners = 0
        loosers = 0
        equities = 0

        best_serie = 0
        worst_serie = 0

        prev_gp = 0

        count_best = 0
        count_worst = 0

        # chart data
        arr_balances = []
        arr_gain_loss_pips = []
        arr_gain_loss_currency = []
        arr_gain_loss_currency_name = []
        arr_gain_loss_account_currency = []
        arr_gain_loss_rates = []

        #
        # log trades as tab separated format
        #

        log_name = "%s_%s_trades.log" % (self._create_time.strftime('%Y%m%dT%H-%M-%S'), self._trader.name)
        log_o = open(self._trader.service.report_path + "/" + log_name, "wt")

        # header
        log_o.write('\t'.join(('ID', 'TYPE', 'DIRECTION', 'MARKET', 'QUANTITY', 'TRANSACT', 'PL_PIP', 'PL_PERCENT', 'PL_CURRENCY', 'BALANCE')) + '\n')

        pc_sum = 0
        for entry in self._history:
            arr_balances.append(entry.balance)

            arr_gain_loss_pips.append(entry.gain_loss_pip)
            arr_gain_loss_currency.append(entry.gain_loss_currency)
            arr_gain_loss_rates.append(entry.gain_loss_rate)
            arr_gain_loss_currency_name.append(entry.order.symbol)
            arr_gain_loss_account_currency.append(entry.gain_loss_account_currency)

            if entry.gain_loss_pip is not None:
                pc_sum += entry.gain_loss_rate

                worst_loss = min(worst_loss, entry.gain_loss_account_currency)
                best_profit = max(best_profit, entry.gain_loss_account_currency)

                if entry.gain_loss_pip > 0:
                    winners += 1
                    
                    if prev_gp > 0:
                        count_best += 1
                        count_worst = 1
                    
                    prev_gp = +1

                elif entry.gain_loss_pip < 0:
                    loosers += 1

                    if prev_gp < 0:
                        count_worst += 1
                        count_best = 1

                    prev_gp = -1

                else:
                    equities += 1
                    prev_gp = 0

                best_serie = max(best_serie, count_best)
                worst_serie = max(worst_serie, count_worst)

                prev_gp = entry.gain_loss_pip

            log_o.write(entry.report(currency) + '\n')

        log_o.close()
        log_o = None

        #
        # log report
        #

        # conversion in account currency are done at the same market price, so its very approximative
        log_name = "%s_%s_report.log" % (self._create_time.strftime('%Y%m%dT%H-%M-%S'), self._trader.name)
        log_o = open(self._trader.service.report_path + "/" + log_name, "wt")

        log_o.write("# Note that conversion in account currency are done at the same market price, so its very approximative.\n")
        log_o.write("- Total %.2f%% with %s trades\n" % (pc_sum, len(self._history)))
        log_o.write("- Best profit %.2f%s / Worst loss %.2f%s\n" % (best_profit, currency, worst_loss, currency))
        log_o.write("- Winners %s / Loosers %s / Equities %s\n" % (winners, loosers, equities))
        log_o.write("- Best serie len %s / Worst serie len %s\n" % (best_serie, worst_serie))

        log_o.close()
        log_o = None

        #
        # log py data (useful to chart them)
        #

        log_name = "%s_%s_data.py" % (self._create_time.strftime('%Y%m%dT%H-%M-%S'), self._trader.name)
        log_o = open(self._trader.service.report_path + "/" + log_name, "wt")

        log_o.write("balances = %s\n\n" % repr(arr_balances))
        log_o.write("profit_loss_pips = %s\n\n" % repr(arr_gain_loss_pips))
        log_o.write("profit_loss_currency = %s\n\n" % repr(arr_gain_loss_currency))
        log_o.write("profit_loss_rates = %s\n\n" % repr(arr_gain_loss_rates))
        log_o.write("profit_loss_currency_name = %s\n\n" % repr(arr_gain_loss_currency_name))
        log_o.write("profit_loss_account_currency = %s\n\n" % repr(arr_gain_loss_account_currency))

        log_o.close()
        log_o = None

    def get_live_report(self):
        """
        Returns live performance in an array. 
        """
        results = []

        for k, rate in self._live_rate.items():
            results.append((k, rate[0], rate[1]))

        return results
