# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Fetcher interface

import time

from datetime import datetime, timedelta

from common.utils import matching_symbols_set, timeframe_to_str, UTC
from terminal.terminal import Terminal

from instrument.instrument import Tick, Candle, Instrument
from instrument.candlegenerator import CandleGenerator

from common.signal import Signal
from database.database import Database

from trader.market import Market

import logging
logger = logging.getLogger('siis.fetcher')


class Fetcher(object):
    """
    Fetcher base class.
    Fetch trade if support else candles of a base timeframe, and then generate the higher candle according to

    GENERATED_TF list (from 1 sec to 1 week).

    @todo Manage the case of 3m because, high 5m is not a multiple of 3m, so 5m need 1m like 3m, but
        the method remove the 1m generated candle once used for the 3m, maybe use a ref counter
    """

    # candles from 1m to 1 week
    # GENERATED_TF = [60, 60*3, 60*5, 60*15, 60*30, 60*60, 60*60*2, 60*60*4, 60*60*24, 60*60*24*7]
    GENERATED_TF = [60, 60*5, 60*15, 60*30, 60*60, 60*60*2, 60*60*4, 60*60*24, 60*60*24*7]

    TICK_STORAGE_DELAY = 0.05  # 50ms
    MAX_PENDING_TICK = 10000

    def __init__(self, name, service):
        super().__init__()

        self._name = name
        self._service = service

        self._available_instruments = set()

        self._last_ticks = []
        self._last_ohlcs = {}

    @property
    def service(self):
        return self._service

    @property
    def name(self):
        return self._name
    
    def has_instrument(self, instrument, fetch_option=""):
        return instrument in self._available_instruments

    def available_instruments(self):
        return self._available_instruments

    def matching_symbols_set(self, configured_symbols, available_symbols):
        """
        Special '*' symbol mean every symbol.
        Starting with '!' mean except this symbol.
        Starting with '*' mean every wildchar before the suffix.

        @param available_symbols List containing any supported markets symbol of the broker. Used when a wildchar is defined.
        """
        if not available_symbols:
            return configured_symbols

        return matching_symbols_set(configured_symbols, available_symbols)

    def connect(self):
        pass

    def disconnect(self):
        pass

    @property
    def connected(self):
        return False

    def fetch_and_generate(self, market_id, timeframe, from_date=None, to_date=None, n_last=1000, fetch_option="", cascaded=None):
        if timeframe > 0 and timeframe not in self.GENERATED_TF:
            logger.error("Timeframe %i is not allowed !" % (timeframe,))
            return

        generators = []
        from_tf = timeframe

        self._last_ticks = []
        self._last_ohlcs = {}

        if not from_date and n_last:
            # compute a from date
            today = datetime.now().astimezone(UTC())

            if timeframe >= Instrument.TF_MONTH:
                from_date = (today - timedelta(months=int(timeframe/Instrument.TF_MONTH)*n_last)).replace(day=1).replace(hour=0).replace(minute=0).replace(second=0)
            elif timeframe >= Instrument.TF_1D:
                from_date = (today - timedelta(days=int(timeframe/Instrument.TF_1D)*n_last)).replace(hour=0).replace(minute=0).replace(second=0)
            elif timeframe >= Instrument.TF_1H:
                from_date = (today - timedelta(hours=int(timeframe/Instrument.TF_1H)*n_last)).replace(minute=0).replace(second=0)
            elif timeframe >= Instrument.TF_1M:
                from_date = (today - timedelta(minutes=int(timeframe/Instrument.TF_1M)*n_last)).replace(second=0)
            elif timeframe >= Instrument.TF_1S:
                from_date = (today - timedelta(seconds=int(timeframe/Instrument.TF_1S)*n_last))

            from_date = from_date.replace(microsecond=0)

        if not to_date:
            today = datetime.now().astimezone(UTC())

            if timeframe == Instrument.TF_MONTH:
                to_date = today + timedelta(months=1)
            else:
                to_date = today + timedelta(seconds=timeframe)

            to_date = to_date.replace(microsecond=0)

        # cascaded generation of candles
        if cascaded:
            for tf in Fetcher.GENERATED_TF:
                if tf > timeframe:
                    # from timeframe greater than initial
                    if tf <= cascaded:
                        # until max cascaded timeframe
                        generators.append(CandleGenerator(from_tf, tf))
                        from_tf = tf

                        # store for generation
                        self._last_ohlcs[tf] = []
                else:
                    from_tf = tf

        if timeframe > 0:
            self._last_ohlcs[timeframe] = []

        n = 0
        t = 0
        data = None

        if timeframe == 0:
            for data in self.fetch_trades(market_id, from_date, to_date, None):
                # store (int timestamp in ms, str bid, str ofr, str volume)
                Database.inst().store_market_trade((self.name, market_id, data[0], data[1], data[2], data[3]))

                if generators:
                    self._last_ticks.append((float(data[0]) * 0.001, float(data[1]), float(data[2]), float(data[3])))

                # generate higher candles
                for generator in generators:
                    if generator.from_tf == 0:
                        candles = generator.generate_from_ticks(self._last_ticks)

                        if candles:
                            for c in candles:
                                self.store_candle(market_id, generator.to_tf, c)

                            self._last_ohlcs[generator.to_tf] += candles

                        # remove consumed ticks
                        self._last_ticks = []
                    else:
                        candles = generator.generate_from_candles(self._last_ohlcs[generator.from_tf])

                        if candles:
                            for c in candles:
                                self.store_candle(market_id, generator.to_tf, c)

                            self._last_ohlcs[generator.to_tf] += candles

                        # remove consumed candles
                        self._last_ohlcs[generator.from_tf] = []

                n += 1
                t += 1

                if n == 10000:
                    n = 0
                    Terminal.inst().info("%i trades for %s, latest %s UTC..." % (
                        t, market_id,
                        datetime.fromtimestamp(float(data[0]) * 0.001, tz=UTC()).strftime('%Y-%m-%dT%H:%M:%S.%f')))

                # calm down the storage of tick, if parsing is faster
                while Database.inst().num_pending_ticks_storage() > Fetcher.MAX_PENDING_TICK:
                    time.sleep(Fetcher.TICK_STORAGE_DELAY)  # wait a little before continue

            if data:
                logger.info("Fetched %i trades for %s, latest %s UTC" % (
                    t, market_id,
                    datetime.fromtimestamp(float(data[0]) * 0.001, tz=UTC()).strftime('%Y-%m-%dT%H:%M:%S.%f')))

        elif timeframe > 0:
            for data in self.fetch_candles(market_id, timeframe, from_date, to_date, None):
                # store (int timestamp ms, str open bid, high bid, low bid, close bid, open ofr, high ofr, low ofr, close ofr, volume)
                Database.inst().store_market_ohlc((
                    self.name, market_id, data[0], int(timeframe),
                    data[1], data[2], data[3], data[4],
                    data[5], data[6], data[7], data[8],
                    data[9]))

                if generators:
                    candle = Candle(float(data[0]) * 0.001, timeframe)

                    candle.set_bid_ohlc(float(data[1]), float(data[2]), float(data[3]), float(data[4]))
                    candle.set_ofr_ohlc(float(data[5]), float(data[6]), float(data[7]), float(data[8]))

                    candle.set_volume(float(data[9]))
                    candle.set_consolidated(True)

                    self._last_ohlcs[timeframe].append(candle)

                # generate higher candles
                for generator in generators:
                    candles = generator.generate_from_candles(self._last_ohlcs[generator.from_tf])
                    if candles:
                        for c in candles:
                            self.store_candle(market_id, generator.to_tf, c)

                        self._last_ohlcs[generator.to_tf].extend(candles)

                    # remove consumed candles
                    self._last_ohlcs[generator.from_tf] = []

                n += 1
                t += 1

                if n == 1000:
                    n = 0
                    Terminal.inst().info("%i OHLCs for %s in %s, latest %s UTC..." % (
                        t, market_id, timeframe_to_str(timeframe),
                        datetime.fromtimestamp(float(data[0]) * 0.001, tz=UTC()).strftime('%Y-%m-%dT%H:%M:%S')))

            if data:
                logger.info("Fetched %i OHLCs for %s in %s, latest %s UTC" % (
                    t, market_id, timeframe_to_str(timeframe),
                    datetime.fromtimestamp(float(data[0]) * 0.001, tz=UTC()).strftime('%Y-%m-%dT%H:%M:%S')))

    def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None):
        """
        Retrieve the historical trades data for a certain a period of date.
        @param market_id Specific name of the market
        @param from_date
        @param to_date
        """
        pass

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        """
        Retrieve the historical candles data for an unit of time and certain a period of date.
        @param market_id Specific name of the market
        @param timeframe Time unit in second.
        @param from_date
        @param to_date
        @param n_last Last n data
        """
        pass

    def store_candle(self, market_id, timeframe, candle):
        Database.inst().store_market_ohlc((
            self.name, market_id, int(candle.timestamp*1000.0), int(timeframe),
            str(candle.bid_open), str(candle.bid_high), str(candle.bid_low), str(candle.bid_close),
            str(candle.ofr_open), str(candle.ofr_high), str(candle.ofr_low), str(candle.ofr_close),
            str(candle.volume)))

    def install_market(self, market_id):
        """
        From what is locally defined install the market data for a specific market id
        """
        pass

    def install_market_data(self, market_id, market_data):
        """
        Install a market info data into the database.
        """
        market = Market(market_id, market_data.get('symbol', market_id))

        market.base_exchange_rate = market_data.get('base-exchange-rate', 1.0)

        market.one_pip_means = market_data.get('one-pip-means', 1.0)
        market.value_per_pip = market_data.get('value-per-pip', 1.0)
        market.contract_size = market_data.get('contract-size', 1.0)
        market.lot_size = market_data.get('lot-size', 1.0)

        market.expiry = market_data.get('expiry', '-')

        base = market_data.get('base', {})
        market.set_base(base.get('symbol', 'USD'), base.get('display', '$'), base.get('precision', 2))

        quote = market_data.get('quote', {})
        market.set_base(quote.get('symbol', 'USD'), quote.get('display', '$'), quote.get('precision', 2))

        market.is_open = True

        market.margin_factor = market_data.get('margin-factor', 1.0)

        if 'unit' in market_data:
            if market_data['unit'] == 'amount':
                market.unit_type = Market.UNIT_AMOUNT
            elif market_data['unit'] == 'contracts':
                market.unit_type = Market.UNIT_CONTRACTS
            elif market_data['unit'] == 'shares':
                market.unit_type = Market.UNIT_SHARES
            else:
                market.unit_type = Market.UNIT_CONTRACTS
        else:
            market.unit_type = Market.UNIT_CONTRACTS

        if 'type' in market_data:
            if market_data['type'] == 'currency':
                market.market_type = Market.TYPE_CURRENCY
            elif market_data['type'] == 'indice':
                market.market_type = Market.TYPE_INDICE
            elif market_data['type'] == 'commodity':
                market.market_type = Market.TYPE_COMMODITY
            elif market_data['type'] == 'stock':
                market.market_type = Market.TYPE_STOCK
            elif market_data['type'] == 'rate':
                market.market_type = Market.TYPE_RATE
            elif market_data['type'] == 'sector':
                market.market_type = Market.TYPE_SECTOR
            else:
                market.market_type = Market.TYPE_UNKNOWN
        else:
            market.market_type = Market.TYPE_UNKNOWN

        if 'contract' in market_data:
            if market_data['contract'] == 'spot':
                market.contract_type = Market.CONTRACT_SPOT
            elif market_data['contract'] == 'cfd':
                market.contract_type = Market.CONTRACT_CFD
            elif market_data['contract'] == 'futur':
                market.contract_type = Market.CONTRACT_FUTUR
            elif market_data['contract'] == 'option':
                market.contract_type = Market.CONTRACT_OPTION
            elif market_data['contract'] == 'warrant':
                market.contract_type = Market.CONTRACT_WARRANT
            elif market_data['contract'] == 'turbo':
                market.contract_type = Market.CONTRACT_TURBO
            else:
                market.contract_type = Market.CONTRACT_SPOT
        else:
            market.contract_type = Market.CONTRACT_SPOT

        market.trade = 0

        if market_data.get('spot', False):
            market.trade |= Market.TRADE_BUY_SELL
        if market_data.get('margin', False):
            market.trade |= Market.TRADE_MARGIN
        if market_data.get('indivisible', False):
            market.trade |= Market.TRADE_IND_MARGIN
        if market_data.get('fifo', False):
            market.trade |= Market.TRADE_FIFO
        if market_data.get('position', False):
            market.trade |= Market.TRADE_POSITION

        orders = market_data.get('orders', ('market', 'limit', 'stop-market', 'stop-limit', 'take-profit-market', 'take-profit-limit'))

        if 'market' in orders:
            market.orders |= Market.ORDER_MARKET
        if 'limit' in orders:
            market.orders |= Market.ORDER_LIMIT
        if 'stop-market' in orders:
            market.orders |= Market.ORDER_STOP_MARKET
        if 'stop-limit' in orders:
            market.orders |= Market.ORDER_STOP_LIMIT
        if 'take-profit-market' in orders:
            market.orders |= Market.ORDER_TAKE_PROFIT_MARKET
        if 'take-profit-limit' in orders:
            market.orders |= Market.ORDER_TAKE_PROFIT_LIMIT
        if 'one-cancel-other' in orders:
            market.orders |= Market.ORDER_ONE_CANCEL_OTHER

        size_limits = market_data.get('size-limits', {'min': 0.0, 'max': 0.0, 'step': 0.0})
        market.set_size_limits(size_limits.get('min', 0.0), size_limits.get('max', 0.0), size_limits.get('step', 0.0))

        notional_limits = market_data.get('notional-limits', {'min': 0.0, 'max': 0.0, 'step': 0.0})
        market.set_size_limits(notional_limits.get('min', 0.0), notional_limits.get('max', 0.0), notional_limits.get('step', 0.0))

        price_limits = market_data.get('price-limits', {'min': 0.0, 'max': 0.0, 'step': 0.0})
        market.set_size_limits(price_limits.get('min', 0.0), price_limits.get('max', 0.0), price_limits.get('step', 0.0))

        # fees & commissions
        fees = market_data.get('fees', {})
        market.maker_fee = fees.get('maker', 0.0)
        market.taker_fee = fees.get('taker', 0.0)

        commissions = market_data.get('commissions', {})
        market.maker_commission = commissions.get('maker', 0.0)
        market.taker_commission = commissions.get('maker', 0.0)

        # store the last market info to be used for backtesting
        Database.inst().store_market_info((self.name, market.market_id, market.symbol,
            market.market_type, market.unit_type, market.contract_type,  # type
            market.trade, market.orders,  # type
            market.base, market.base_display, market.base_precision,  # base
            market.quote, market.quote_display, market.quote_precision,  # quote
            market.expiry, int(market.last_update_time * 1000.0),  # expiry, timestamp
            str(market.lot_size), str(market.contract_size), str(market.base_exchange_rate),
            str(market.value_per_pip), str(market.one_pip_means), str(market.margin_factor),
            str(market.min_size), str(market.max_size), str(market.step_size),  # size limits
            str(market.min_notional), str(market.max_notional), str(market.step_notional),  # notional limits
            str(market.min_price), str(market.max_price), str(market.tick_price),  # price limits
            str(market.maker_fee), str(market.taker_fee), str(market.maker_commission), str(market.taker_commission))  # fees
        )
