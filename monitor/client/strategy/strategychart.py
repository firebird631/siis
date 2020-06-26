# @date 2019-01-01
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Standard strategy charting

import time
import copy

import numpy as np

from datetime import datetime
from terminal.terminal import Terminal
from trader.order import Order

from monitor.streamable import Streamable, StreamMemberSerie, StreamMemberFloatSerie, StreamMemberFloatScatter, \
    StreamMemberFloatBarSerie, StreamMemberOhlcSerie

from matplotlib.dates import epoch2num

from charting.charting import Charting

import logging
logger = logging.getLogger('siis.client.strategychart')


COLOR_MAP = {
    0: 'blue',
    1: 'green',
    2: 'red',
    3: 'cyan',
    4: 'magenta',
    5: 'yellow',
    6: 'black',
    7: '#777777',
}

def name_to_color(name):
    s = 0
    i = 0

    if name == 'price':
        return COLOR_MAP[7]

    for c in name:
        s += (ord(c) >> i) ** ord(c)
        i += 1

    s = s % len(COLOR_MAP)

    return COLOR_MAP[s]


class StrategyChartBase(object):

    def __init__(self, name, chart_type):
        self.name = name
        self.chart_type = chart_type


class StrategyChartSerie(StrategyChartBase):

    CHART_SERIE = 1

    def __init__(self, i, ii, name, values=None):
        super().__init__(name, StrategyChartSerie.CHART_SERIE)

        self.last = 0.0
        self.i = i
        self.ii = ii
        self.v = values or []
        self.c = name_to_color(name)


class StrategyChartScatter(StrategyChartBase):

    CHART_SCATTER = 2

    def __init__(self, i, ii, name, glyph, values=None):
        super().__init__(name, StrategyChartScatter.CHART_SCATTER)

        self.last = 0.0
        self.i = i
        self.ii = ii
        self.v = values or []
        self.glyph = glyph


class StrategyChartBarSerie(StrategyChartBase):

    CHART_BAR_SERIE = 3

    def __init__(self, i, ii, name, values=None):
        super().__init__(name, StrategyChartBarSerie.CHART_BAR_SERIE)

        self.last = 0.0
        self.i = i
        self.ii = ii
        self.v = values or []
        self.c = name_to_color(name)


class StrategyChartOhlcSerie(StrategyChartBase):

    CHART_OHLC_SERIE = 4

    def __init__(self, name, width):
        super().__init__(name, StrategyChartOhlcSerie.CHART_OHLC_SERIE)

        self.last = 0.0
        self.v = [(np.NaN, np.NaN, np.NaN, np.NaN)]*width
        # self.v = [(np.NaN, np.NaN, np.NaN, np.NaN, np.NaN)]*width


class StrategyChart(object):

    DEFAULT_WINDOW_SIZE = 180  # 1h30 if 1m resolution
    MAX_SUB_CHARTS = 16

    @staticmethod
    def create_chart(data):
        if data['c'] == Streamable.STREAM_STRATEGY_CHART:
            chart = StrategyChart(data['g'], data['s'])
            return chart

        return None

    def __init__(self, group_name, stream_name):
        self.chart = None

        self.strategy_identifier = group_name
        parts = stream_name.split(':')

        self.instrument_symbol = parts[0]
        self.tf = int(parts[1])

        self.depth = 0
        self.history = 0

        self.candles = None
        self.series = {}
        self.scatters = {}
        self.labels = {}
        self.plots = {}
        self.series_count = [0]*StrategyChart.MAX_SUB_CHARTS
        self.scatters_count = [0]*StrategyChart.MAX_SUB_CHARTS
        self.bars_count = [0]*StrategyChart.MAX_SUB_CHARTS

        self.window = StrategyChart.DEFAULT_WINDOW_SIZE

        self.begin = None
        self.range = [0, 0]

        self._visible = True

    def unchart(self):
        if self.chart:
            self._visible = False

            Charting.inst().remove_chart(self.chart)
            self.chart = None

    @property
    def key(self):
        return "%s:%i" % (self.instrument_symbol, self.tf)
    
    def on_chart(self, data):
        # <strategy-identifier>
        if data['g'] != self.strategy_identifier:
            return

        # <market>:<tf> or <market> in case of multi-timeframe data
        if data['s'] != self.key and not self.key.startswith(data['s']+':'):
            return

        if self.chart is None and Charting.inst() and self._visible:
            # create the chart if necessary
            self.chart = Charting.inst().chart("%s on %s (%i)" % (self.strategy_identifier, self.instrument_symbol, self.tf))

        rechart = False

        if self.chart:
            if data['t'] == StreamMemberSerie.TYPE_SERIE:
                if data['n'] == 'begin' and data['v'] >= self.range[1]:
                    # begin a new frame (replace last or more recent)
                    self.begin = data['v']

                    if self.range[0] == 0:
                        # initial left range value
                        self.range[0] = data['v'] - self.window * self.tf

                    # last right range value
                    self.range[1] = data['v']

                elif data['n'] == 'end' and data['v'] >= self.range[1]:
                    # end of the frame (last or more recent)
                    self.begin = None

                    # limit range to window
                    if int((self.range[1] - self.range[0]) / self.tf) > self.window:
                        self.range[0] = self.range[1] - self.window * self.tf

                    # query for rechart
                    rechart = True

                # @todo why data issue in backtesting ?
                # logger.info(datetime.fromtimestamp(data['v']).strftime('%Y-%m-%d %H:%M:%S'))

            elif data['t'] == StreamMemberOhlcSerie.TYPE_OHLC_SERIE:
                if self.begin and data['b'] == self.begin:
                    # append for the current serie timestamp
                    if not self.candles:
                        self.candles = StrategyChartOhlcSerie(data['n'], self.window)

                    # append or replace according to timestamp
                    candles = self.candles
                    if candles and candles.v and candles.last == self.begin:
                        # replace the last @todo to avoid later conversion
                        # candles.v[-1] = (epoch2num(data['b']), *data['v'])
                        candles.v[-1] = data['v']
                    else:
                        # append and keep the window width
                        # candles.v.append((epoch2num(data['b']), *data['v']))
                        candles.v.append(data['v'])
                        candles.v.pop(0)
                        candles.last = self.begin

            elif data['t'] == StreamMemberFloatSerie.TYPE_FLOAT_SERIE:
                if self.begin and data['b'] == self.begin:
                    # append for the current serie timestamp
                    if data['n'] not in self.series:
                        self.series[data['n']] = StrategyChartSerie(data['i'], self.series_count[data['i']], data['n'], [np.NaN]*self.window)
                        self.series_count[data['i']] += 1

                    # append or replace according to timestamp
                    serie = self.series.get(data['n'])
                    if serie and serie.v and serie.last == self.begin:
                        # replace the last
                        serie.v[-1] = data['v']
                    else:
                        # append and keep the window width
                        serie.v.append(data['v'])
                        serie.v.pop(0)
                        serie.last = self.begin

            elif data['t'] == StreamMemberFloatBarSerie.TYPE_FLOAT_BAR_SERIE:
                if self.begin and data['b'] == self.begin:
                    if data['n'] not in self.series:
                        self.series[data['n']] = StrategyChartBarSerie(data['i'], self.bars_count[data['i']], data['n'], [np.NaN]*self.window)
                        self.bars_count[data['i']] += 1

                    # append or replace according to timestamp
                    serie = self.series.get(data['n'])
                    if serie and serie.v and serie.last == self.begin:
                        # replace the last
                        serie.v[-1] = data['v']
                    else:
                        # append and keep the window width
                        serie.v.append(data['v'])
                        serie.v.pop(0)
                        serie.last = self.begin

            elif data['t'] == StreamMemberFloatScatter.TYPE_FLOAT_SCATTER:
                if data['b'] >= self.range[0]:
                    # append for the current serie timestamp
                    if data['n'] not in self.scatters:
                        self.scatters[data['n']] = StrategyChartScatter(data['i'], self.scatters_count[data['i']], data['n'], data['o'])
                        self.scatters_count[data['i']] += 1

                    # append the tuple
                    scatter = self.scatters.get(data['n'])
                    scatter.v.append((datetime.fromtimestamp(data['b']), data['v']))

                    # keep only scatter into the window range
                    while scatter.v and scatter.v[0][0].timestamp() < self.range[0]:
                        scatter.v.pop(0)

                    # query for rechart
                    rechart = True

            # can now rechart
            if rechart:
                self.purge()
                self.rechart()

    def purge(self):
        # remove scatters out of the window range
        for k, scatter in self.scatters.items():
            while scatter.v and scatter.v[0][0].timestamp() < self.range[0]:
                scatter.v.pop(0)

    def rechart(self):
        rechart = False

        if self.chart is None:
            return

        if not Charting.inst().visible:
            return

        self.chart.lock()

        # width = int((self.range[1] - self.range[0]) / self.tf)
        self.chart.set_range(self.range[0], self.range[1], self.tf)

        if self.candles:
            self.chart.set_candles(self.candles.v, width=1/(self.window*15)*(self.tf/60))
            # self.chart.set_candles2(self.candles.v, width=1/(self.window*10))

        for n, serie in self.series.items():
            if serie.chart_type == StrategyChartSerie.CHART_SERIE:
                if serie.i == 0:
                    self.chart.plot_price_serie(serie.ii, serie.v, c=serie.c)
                else:
                    self.chart.plot_serie(serie.i, serie.ii, serie.v, label=serie.name, c=serie.c)

            elif serie.chart_type == StrategyChartBarSerie.CHART_BAR_SERIE:
                self.chart.bar_serie(serie.i, serie.ii, serie.v, label=serie.name, c=serie.c, width=1/(self.window*10)*(self.tf/60))

        for n, scatter in self.scatters.items():
            if scatter.i == 0:
                self.chart.scatter_price(scatter.ii, scatter.v, scatter.glyph)
            else:
                self.chart.scatter_serie(scatter.i, scatter.ii, scatter.v, scatter.glyph)

        #       if sub.triangle_bottom:
        #           for b in reversed(sub.triangle_bottom):
        #               if b[0] + self.chart.depth*self.chart.tf >= self.chart.last_timestamp:
        #                   self.chart.triangle_bottom.insert(0, (datetime.fromtimestamp(b[0]), b[1]))
        #               else:
        #                   break

        #       if sub.triangle_top:
        #           for t in reversed(sub.triangle_top):
        #               if t[0] + self.chart.depth*self.chart.tf >= self.chart.last_timestamp:
        #                   self.chart.triangle_top.insert(0, (datetime.fromtimestamp(t[0]), t[1]))
        #               else:
        #                   break

        #       # if sub.pivots:
        #       #   for b in reversed(sub.pivots):
        #       #       if [0] + self.chart.depth*self.chart.tf >= self.chart.last_timestamp:
        #       #           ts = 
        #       #           self.chart.pivots.insert(0, (datetime.fromtimestamp(ts), b))
        #       #       else:
        #       #           break

        #       # if sub.supports:
        #       #   for b in reversed(sub.supports):
        #       #       if b[0] + self.chart.depth*self.chart.tf >= self.chart.last_timestamp:
        #       #           self.chart.supports.insert(0, (datetime.fromtimestamp(b[0]), b[1]))
        #       #       else:
        #       #           break

        #       # if sub.resistances:
        #       #   for t in reversed(sub.resistances):
        #       #       if t[0] + self.chart.depth*self.chart.tf >= self.chart.last_timestamp:
        #       #           self.chart.resistances.insert(0, (datetime.fromtimestamp(t[0]), t[1]))
        #       #       else:
        #       #           break

        #       # if self.chart.supports:
        #       #   self.chart.scatter_price(2, self.chart.supports, 'go')
        #       # if self.chart.resistances:
        #       #   self.chart.scatter_price(3, self.chart.resistances, 'ro')

        #       # day tf
        #       day_tf = (self.chart.last_timestamp - self.chart.daily_depth*Instrument.TF_DAY, self.chart.last_timestamp, Instrument.TF_DAY)

        #       # if self.chart.pivot:
        #       #   self.chart.hline_price_serie(0, self.chart.pivot, xaxis=day_tf, linestyle='--', w=Instrument.TF_DAY, c='blue')
        #       # if self.chart.supports:
        #       #   self.chart.hline_price_serie(1, self.chart.supports, xaxis=day_tf, linestyle='--', w=Instrument.TF_DAY, c='red')
        #       # if self.chart.resistances:
        #       #   self.chart.hline_price_serie(2, self.chart.resistances, xaxis=day_tf, linestyle='--', w=Instrument.TF_DAY, c='red')

        #       if self.chart.rsi:
        #           # could multiply to display in percent
        #           self.chart.plot_serie(1, 0, self.chart.rsi)
        #           self.chart.plot_serie(1, 1, [30]*len(self.chart.rsi))
        #           self.chart.plot_serie(1, 2, [70]*len(self.chart.rsi))

        #       # if self.chart.bollinger[0]:
        #       #   self.chart.plot_serie(2, 0, self.chart.bollinger[0])  # bottom
        #       #   self.chart.plot_serie(2, 1, self.chart.bollinger[1])  # middle
        #       #   self.chart.plot_serie(2, 2, self.chart.bollinger[2])  # top

        #       # if self.chart.triangle_bottom:
        #       #   self.chart.scatter_serie(2, 0, self.chart.triangle_bottom, 'g/')
        #       # if self.chart.triangle_top:
        #       #   self.chart.scatter_serie(2, 1, self.chart.triangle_top, 'r/')

        self.chart.draw()
        self.chart.unlock()
