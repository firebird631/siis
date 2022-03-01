# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Charting handler

import copy
import time
import threading

import numpy as np
import matplotlib

matplotlib.use('Qt5Agg')

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.animation as animation

from datetime import datetime, timedelta
from matplotlib.dates import date2num

from mpl_finance import candlestick_ohlc, candlestick2_ohlc, volume_overlay2

from terminal.terminal import Terminal


class SubChart(object):

	def __init__(self, subchart_id, main_label=""):
		self.subchart_id = subchart_id
		self.main_label = main_label
		self.xaxis = np.array([0])  # main xaxis data
		self.candles = None         # tuple with (ohlc arrays)
		self.plots = [None]*8       # max of 8 plots per subchart
		self.bars = [None]*2        # max of 2 bars per subchart
		self.scatters = [None]*4    # max of 4 scatters per subchart
		self.hlines = [None]*4      # max of 4 horizontal lines
		self.axis = None

	def destroy(self):
		self.axis = None

	def set_candles(self, ohlc, width=None):
		if ohlc is None:
			self.candles = None
		else:
			data = []
			for x in range(0, len(ohlc)):
				data.append((date2num(self.xaxis[x]), *ohlc[x]))

			self.candles = (data, width)

	# def set_candles2(self, data, width=None):
	# 	if data is None:
	# 		self.candles = None
	# 	else:
	# 		self.candles = (copy.copy(data), width)			

	def plot_main_serie(self, data, c=None, xaxis=None, linestyle='-'):
		if data is None:
			self.plots[0] = None
		else:
			self.plots[0] = (copy.copy(data), None, self.main_label, c, xaxis, linestyle)

	def plot_serie(self, plot_id, data, opt=None, label="", c=None, xaxis=None, linestyle='-'):
		if plot_id >= len(self.plots):
			return

		if data is None:
			self.plots[plot_id] = None
		else:
			self.plots[plot_id] = (copy.copy(data), opt, label, c, xaxis, linestyle)

	def bar_main_serie(self, data, c=None, xaxis=None, width=None):
		if data is None:
			self.bars[0] = None
		else:
			self.bars[0] = (copy.copy(data), None, self.main_label, c, xaxis, width)

	def bar_serie(self, bar_id, data, label="", c=None, xaxis=None, width=None):
		if bar_id >= len(self.bars):
			return

		if data is None:
			self.bars[0] = None
		else:
			self.bars[0] = (copy.copy(data), None, label, c, xaxis, width)

	def hline_serie(self, hline_id, data, opt=None, label="", c=None, xaxis=None, linestyle='-', w=1.0):
		if hline_id >= len(self.hlines):
			return

		if data is None:
			self.hlines[hline_id] = None
		else:
			self.hlines[hline_id] = (copy.copy(data), opt, label, c, xaxis, linestyle, w)

	def scatter(self, sca_id, data, style):
		if sca_id >= len(self.scatters):
			return

		if data is None:
			self.scatters[sca_id] = None
		else:
			self.scatters[sca_id] = (copy.copy(data), style)

	def render(self, ticks=False):
		# fig = plt.gcf()
		ax = plt.subplot(511 + self.subchart_id)
		self.axis = ax

		plt.title(self.main_label)
		plt.subplots_adjust(bottom=0.0, right=0.99, top=0.97, left=0.04, hspace=0.325)
		# plt.xlabel('time')
		# # ax.xaxis_date()

		# grid in background
		plt.grid(zorder=0)

		for d in self.plots:
			if d is not None:
				if d[1]:
					plt.plot(d[4] or self.xaxis, d[0], d[1], c=d[3], linestyle=d[5])
				else:
					plt.plot(d[4] or self.xaxis, d[0], c=d[3], linestyle=d[5])

				plt.ylabel(d[2])

		if self.candles:
			candlestick_ohlc(ax, self.candles[0], width=self.candles[1] or 0.0003, colorup='#aaaaaa', colordown='#444444', alpha=1.0)

		for d in self.hlines:
			if d is not None:
				xaxis = d[4] or self.xaxis
				xmin = [x for x in xaxis]
				xmax = [x+timedelta(seconds=d[6]) for x in xaxis]

				plt.hlines(y=d[0], xmin=xmin, xmax=xmax, colors=d[3], linestyle=d[5], linewidth=1.0)

		for scatter in self.scatters:
			if scatter is not None:
				x = [d[0] for d in scatter[0]]

				if scatter[1] == 'g^':
					# green triangle down
					y = [d[1]*1.00008 for d in scatter[0]]
					plt.scatter(x, y, c="g", s=100, alpha=1.0, marker='^', zorder=100)  # caretup
				elif scatter[1] == 'r^':
					# red triangle up
					y = [d[1]*0.99992 for d in scatter[0]]
					plt.scatter(x, y, c="r", s=100, alpha=1.0, marker='v', zorder=100)  # caretdown

				elif scatter[1] == 'g-':
					# green line
					y = [d[1]*1.00008 for d in scatter[0]]
					plt.scatter(x, y, c="g", s=10, alpha=1.0, marker='_', zorder=99)
				elif scatter[1] == 'r-':
					# red line
					y = [d[1]*0.99992 for d in scatter[0]]
					plt.scatter(x, y, c="r", s=10, alpha=1.0, marker='_', zorder=99)

				elif scatter[1] == 'go':
					# green line
					y = [d[1]*1.00001 for d in scatter[0]]
					plt.scatter(x, y, c="g", s=10, alpha=1.0, marker='o', zorder=99)
				elif scatter[1] == 'ro':
					# red line
					y = [d[1]*0.99999 for d in scatter[0]]
					plt.scatter(x, y, c="r", s=10, alpha=1.0, marker='o', zorder=99)

				elif scatter[1] == 'r/':
					# red trend
					y = [d[1] for d in scatter[0]]
					plt.plot(x, y, ".r-", zorder=99)
				elif scatter[1] == 'g/':
					# green trend
					y = [d[1] for d in scatter[0]]
					plt.plot(x, y, ".g-", zorder=99)

		for bar in self.bars:
			if bar is not None:
				plt.bar(bar[4] or self.xaxis, bar[0], width=bar[5] or 0.0005, zorder=10) #, color=bar[3])
				# volume_overlay(ax, opens, closes, volumes, colorup='k', colordown='r', width=4, alpha=1.0) https://matplotlib.org/api/finance_api.html
				# volume_overlay3(ax, quotes, colorup='k', colordown='r', width=4, alpha=1.0)

		# for xy in annotate[0]:
		# 	if annotate[1] == 'g^':
		# 		plt.annotate(' ', xy=xy, xycoords='data', arrowprops=dict(facecolor='green', headwidth=10, headlength=10))
		# 	elif annotate[1] == 'r^':
		# 		plt.annotate(' ', xy=xy, xytext=(xy[0], xy[1]+0.0001), xycoords='data', arrowprops=dict(facecolor='red', headwidth=10, headlength=10))

		if ticks:
			# on the last only
			plt.xticks(rotation=70)
			ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M:%S"))
			# ax.xaxis.set_major_locator(mdates.DateFormatter("%H:%M:%S"))
			# ax.xaxis.set_minor_locator(mdates.DateFormatter("%H:%M:%S"))
		else:
			ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

		return ()


class Chart(object):

	DEFAULT_W = 1400
	DEFAULT_H = 1000

	def __init__(self, name="", uid=0):
		self._name = name
		self._last_charting = 0
		self._draw = True
		self.__active = False

		self._uid = uid
		self._fig = None
		self._ax = None

		self._start = 0
		self._end = 0
		self._step = 1

		self._prices = SubChart(0, "prices")
		self._others = [None]*4

		self._last_redraw = 0

		self._mutex = threading.RLock()
		self._created = False

	def lock(self, blocking=True, timeout=-1):
		self._mutex.acquire(blocking, timeout)

	def unlock(self):
		self._mutex.release()

	def destroy(self):
		for other in self._others:
			if other is not None:
				other.destroy()
		
		if self._prices is not None:
			self._prices.destroy()

		self.destroy_figure()

	def destroy_figure(self):
		if self._fig is not None:
			plt.close(self._fig.number)
			self._ax = None
			self._fig = None		

	@property
	def uid(self):
		return self._uid

	@property
	def fig(self):
		return self._fig

	@property
	def ax(self):
		return self._ax

	@property
	def name(self):
		return self._name

	def create(self, nrows=1):
		self.lock()

		self._fig, self._ax = plt.subplots(nrows=nrows, ncols=1)
		self._fig.canvas.set_window_title(self._name)
		# self._fig.canvas.manager.window.setGeometry(0, Chart.DEFAULT_H-Chart.DEFAULT_H*(self._uid%2)+((1-(self._uid%2))*50), Chart.DEFAULT_W, Chart.DEFAULT_H)
		self._fig.canvas.manager.window.setGeometry(0, 0, Chart.DEFAULT_W, Chart.DEFAULT_H)
		# self._fig.canvas.manager.window.wm_geometry("+%d+%d" % (0, Chart.DEFAULT_H*self._uid))

		plt.figure(self._fig.number)

		def on_move(event):
			fig = plt.gcf()
			chart = Charting.inst().chart_by_figure(fig.number)
			if chart:
				chart.sync_axis(event)

		def on_close(event):
			fig = plt.gcf()
			chart = Charting.inst().chart_by_figure(fig.number)
			if chart:
				chart._fig = None
				chart._ax = None
				chart._created = False  # need to recreate
				Charting.inst().remove_chart(chart)

		plt.connect('close_event', on_close)
		plt.connect('motion_notify_event', on_move)

		self._created = True
		self.unlock()

	def render(self):
		if not self._draw:
			return False

		if not self._created:
			self.create()

		if self._start >= self._end:
			return False

		self._draw = False

		self.lock()

		# fig = plt.gcf()
		# self._fig.canvas.set_window_title(self._name)

		plt.figure(self._fig.number)
		self._fig.clear()

		self._prices.render()

		c = 0

		for other in self._others:
			if other is not None:
				c += 1

		n = 0

		for other in self._others:
			if other is not None:
				other.render(n == c)

			n += 1

		self.unlock()

		return True

	# @property
	# def need_refresh(self):
	# 	if not self.__active:
	# 		return False

	# 	now = time.time()
	# 	if now - self._last_charting >= 1:
	# 		self._last_charting = now
	# 		return Charting.inst() is not None  # and Charting.inst().running

	# 	return False

	def draw(self):
		self._draw = True

	@property
	def need_redraw(self):
		return self._draw

	@property
	def can_redraw(self):
		# can redraw every 10 sec
		if time.time() - self._last_redraw >= 10.0:
			self._last_redraw = time.time()
			return True
		else:
			return False

	@property
	def is_active(self):
		return self.__active

	def _active(self, active):
		if self.__active != active:
			self.__active = active
			self._draw = True  # need redraw

	def set_range(self, start, end, step=1):
		self._start = start
		self._end = end
		self._step = step

		self._prices.xaxis = [datetime.fromtimestamp(x) for x in range(int(self._start), int(self._end), int(self._step))]
		# np.linspace(self._start, self._end, (self._end-self._start)/self._step)

	def set_candles(self, ohlc, width=None):
		self._prices.set_candles(ohlc, width=width)

	def set_candles2(self, data, width=None):
		self._prices.set_candles2(data, width=width)

	def plot_price_serie(self, plot_id, data, opt=None, label="", c=None, xaxis=None, linestyle='-'):
		if plot_id >= 16:
			return

		if xaxis:
			# specific time unit
			spec_xaxis = [datetime.fromtimestamp(x) for x in range(int(xaxis[0]), int(xaxis[1]), int(xaxis[2]))]
		else:
			spec_xaxis = None

		if plot_id == 0:
			self._prices.plot_main_serie(data, c, xaxis=spec_xaxis, linestyle=linestyle)
		elif plot_id > 0:
			self._prices.plot_serie(plot_id, data, opt, label, c, xaxis=spec_xaxis, linestyle=linestyle)

	def hline_price_serie(self, plot_id, data, opt=None, label="", c=None, xaxis=None, linestyle='-', w=1.0):
		if plot_id >= 16:
			return

		if xaxis:
			# specific time unit
			spec_xaxis = [datetime.fromtimestamp(x) for x in range(int(xaxis[0]), int(xaxis[1]), int(xaxis[2]))]
		else:
			spec_xaxis = None

		self._prices.hline_serie(plot_id, data, opt, label, c, xaxis=spec_xaxis, linestyle=linestyle, w=w)

	def scatter_price(self, sca_id, data, style):
		self._prices.scatter(sca_id, data, style)

	def scatter_serie(self, chart_id, sca_id, data, style):
		if chart_id >= 4 or sca_id >= 4:
			return

		if self._others[chart_id] is None:
			self._others[chart_id] = SubChart(chart_id, "sub%s" % chart_id)

		self._others[chart_id].scatter(sca_id, data, style)

	def bar_serie(self, chart_id, bar_id, data, label="", c=None, xaxis=None, width=None):
		if chart_id >= 4 or bar_id >= 2:
			return

		if self._others[chart_id] is None:
			self._others[chart_id] = SubChart(chart_id, label if label else "sub%s" % chart_id)

		# default xaxis to the main time unit
		self._others[chart_id].xaxis = [datetime.fromtimestamp(x) for x in range(int(self._start), int(self._end), int(self._step))]

		if xaxis:
			# specific time unit
			spec_xaxis = [datetime.fromtimestamp(x) for x in range(int(xaxis[0]), int(xaxis[1]), int(xaxis[2]))]
		else:
			spec_xaxis = None

		self._others[chart_id].bar_serie(bar_id, data, label, c, xaxis=spec_xaxis, width=width)

	def plot_serie(self, chart_id, plot_id, data, opt=None, label="", c=None, xaxis=None, linestyle='-'):
		"""
		Same as plot_price serie but on an additional chart.
		"""
		if chart_id >= 4 or plot_id >= 16:
			return

		if self._others[chart_id] is None:
			self._others[chart_id] = SubChart(chart_id, label if label else "sub%s" % chart_id)

		# default xaxis to the main time unit
		self._others[chart_id].xaxis = [datetime.fromtimestamp(x) for x in range(int(self._start), int(self._end), int(self._step))]
		# self._others[chart_id].xaxis = np.linspace(self._start, self._end, (self._end-self._start)/self._step)

		if xaxis:
			# specific time unit
			spec_xaxis = [datetime.fromtimestamp(x) for x in range(int(xaxis[0]*1000), int(xaxis[1]*1000), int(xaxis[2]*1000))]
		else:
			spec_xaxis = None

		if plot_id == 0:
			self._others[chart_id].plot_main_serie(data, c, xaxis=spec_xaxis, linestyle=linestyle)
		else:
			self._others[chart_id].plot_serie(plot_id, data, opt, label, c, xaxis=spec_xaxis, linestyle=linestyle)

	def hline_serie(self, chart_id, hline_id, data, opt=None, label="", c=None, xaxis=None, linestyle='-', w=1.0):
		if chart_id >= 4 or hline_id >= 4:
			return

		if xaxis:
			# specific time unit
			spec_xaxis = [datetime.fromtimestamp(x) for x in range(int(xaxis[0]), int(xaxis[1]), int(xaxis[2]))]
		else:
			spec_xaxis = None

		self._others[chart_id].hline_serie(plot_id, data, opt, label, c, xaxis=spec_xaxis, linestyle=linestyle, w=w)

	# def scatter_price_serie(self, plot_id, data, s=None, c=None, marker='o', cmap=None):
	# 	"""
	# 	@param cmap An array color map.
	# 	"""
	# 	if plot_id >= 16:
	# 		return

	# 	if plot_id == 0:
	# 		self._prices.scatter(0, data, s, c, marker, cmap)
	# 	elif plot_id > 0:
	# 		self._prices.scatter(plot_id, data, s, c, marker, cmap)

	# def scatter_serie(self, chart_id, plot_id, data, s=None, c=None, market='o', cmap=None):
	# 	"""
	# 	Same as scatter_price serie but on an additional chart.
	# 	"""
	# 	if chart_id >= 4 or plot_id >= 16:
	# 		return

	# 	if self._others[chart_id] is None:
	# 		self._others[chart_id] = SubChart(chart_id, "sub%s" % chart_id)			

	# 	if plot_id == 0:
	# 		self._others[chart_id].scatter(0, data, s, c, marker, cmap)
	# 	else:
	# 		self._others[chart_id].scatter(plot_id, data, s, c, marker, cmap)

	def sync_axis(self, event):
		"""
		Sync the axis any plots when there is a change into one on the X axis (pan, zoom).
		"""
		return
		if event.inaxes is None:
			return

		xlim = event.inaxes.get_xlim()
		xb = event.inaxes.get_xbound()

		if event.inaxes == self._prices.axis:
			for other in self._others:
				if other and other.axis:
					other.axis.set_xlim(xlim)
					other.axis.set_xbound(xb)
		else:
			for other in self._others:
				if other and event.inaxes == other.axis:
					if self._prices.axis:
						self._prices.axis.set_xlim(xlim)
						self._prices.axis.set_xbound(xb)

					for other2 in self._others:
						if other != other2:
							if other2 and other2.axis:
								other2.axis.set_xlim(xlim)
								other2.axis.set_xbound(xb)

					break


class Charting(threading.Thread):
	"""
	Multiple chart but not at a time.
	@todo need to create a stream of charting data and a websocket server to recast thoose stream to a webclient with more efficient plotting capacities
	@todo need a display window where the data are sent, and adjust them as they goes outstide of the memory window, so need a memory + a display window
	@todo but the best solution is sending data stream/update throught monitor and then a webclient with good charting API will using a WS display data
	"""
	__instance = None

	@classmethod
	def inst(cls):
		if Charting.__instance is None:
			Charting.__instance = Charting()

		return Charting.__instance

	@classmethod
	def terminate(cls):
		if Charting.__instance is not None:
			Charting.__instance.stop()
			Charting.__instance = None

	def __init__(self):
		super().__init__(name="charting")

		Charting.__instance = self

		self._mutex = threading.RLock()

		self._show = False
		self._hide = False
		self._render = False
		self._visible = False
		self._running = False
		self._rendering = False

		self._charts = {}
		self._next_uid = 1
	
	def lock(self, blocking=True, timeout=-1):
		self._mutex.acquire(blocking, timeout)

	def unlock(self):
		self._mutex.release()

	def chart(self, name):
		self.lock()
		_chart = Chart(name, self._next_uid)
		self._charts[_chart.uid] = _chart

		self._next_uid += 1

		self.unlock()

		return _chart

	def remove_chart(self, chart):
		if chart is not None:
			self.lock()
			del self._charts[chart.uid]
			self.unlock()

	def has_charts(self):
		return len(self._charts) > 0

	def render(self):
		self._render = True

	def show(self):
		if not self._visible:
			self._show = True

	def hide(self):
		if self._visible:
			self._hide = True

	def chart_by_figure(self, number):
		self.lock()
		for k, chart in self._charts.items():
			if chart.fig and chart.fig.number == number:
				self.unlock()
				return chart

		self.unlock()
		return None

	@property
	def visible(self):
		return self._visible

	def run(self):
		plt.ion()

		# remove the default figure
		#plt.close(1)
		# fig = plt.gcf()
		# plt.close(fig.number)

		while self._running:
			if self._show:
				if not self._visible:
					self._visible = True
					plt.show(block=False)

				self._show = False
				self._rendering = True

			elif self._hide:
				if self._visible:
					plt.close('all')
					# self.lock()
					# for k, chart in self._charts.items():
					# 	chart.destroy()
					# self._charts = {}
					# self.unlock()
					self._visible = False

				self._hide = False
				self._rendering = False

			# elif self._cur_char and self._cur_char.need_redraw and self._visible:
			# 	# fig = plt.gcf()
			# 	# fig.clear()

			# 	self.lock()

			# 	if self._cur_char and self._cur_char.is_active:
			# 		self._cur_char.render()

			# 	self.unlock()

			# 	self._render = False
			# 	self._rendering = True

			# 	# fig = None

			if self._visible:
				self.lock()
				for k, chart in self._charts.items():
					if chart.need_redraw:
						chart.render()
				self.unlock()

			if self._visible:
				if self._rendering and len(self._charts):
					# plt.show(block=False)
					try:
						# that suck but it's like it is
						# plt.pause(2.0)
						my_pause(5.0)
						pass
					except:
						pass

		self.lock()
		for k, chart in self._charts.items():
			chart.destroy()
		self.unlock()

		plt.ioff()
		plt.close('all')

	def start(self):
		if not self._running:
			self._running = True
			self.setDaemon(True)
			super().start()

	def stop(self):
		if self._running:
			self._running = False

			if self.is_alive():
				self.join()

	@property
	def running(self):
		return self._running

def my_pause(interval):
	backend = plt.rcParams['backend']
	if backend in matplotlib.rcsetup.interactive_bk:
        figManager = matplotlib._pylab_helpers.Gcf.get_active()
        if figManager is not None:
            canvas = figManager.canvas
            if canvas.figure.stale:
                canvas.draw()
            canvas.start_event_loop(interval)
            return
