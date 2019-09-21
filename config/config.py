# @date 2018-08-08
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Config for : Databases, Fetchers, Watchers, Traders, Indicator, Region, TradeOps, Strategies, Monitoring

# Help
# ----
#
# Considers to make a local .siis/config/config.py file with what you need to overrides.
#
# At least DATABASES, WATCHERS, TRADERS, MONITORING need overrides.
#
# You can add your specifics fetchers, indicators, regions, tradeops, strategies in your local file.
#
# For watchers and traders you can add your specifics models too in your local file, and you should
# overrides the symbols at the profile level in appliance.py file letting symbols list empty in config file.
#
# Take care than a missing symbol from a watcher or trader will cause the impossibility to uses it in a strategy.
# A commented list of symbols here servers as example.

# There is only one database at this time
DATABASES = {
    'siis': {                   # lookup name (do not change)
        'type': 'pgsql',        # pgsql or mysql
        'name': 'siis',         # database name
        'user': 'siis',         # database user grant for siis database
        'password': 'siis',     # user password
        'host': '127.0.0.1',    # database hostname or unix:// socket
        'port': 5432,           # database host port
        'conn_max_age': 86400
    }
}

FETCHERS = {
    'alphavantage.co': {
        'classpath': 'watcher.connector.alphavantage.fetcher.AlphaVantageFetcher',
    },
    'binance.com': {
        'classpath': 'watcher.connector.binance.fetcher.BinanceFetcher',
    },  
    'bitmex.com': {
        'classpath': 'watcher.connector.bitmex.fetcher.BitMexFetcher',
    },
    'ig.com': {
        'classpath': 'watcher.connector.ig.fetcher.IGFetcher',
    },
    'tiingo.com': {
        'classpath': 'watcher.connector.tiingo.fetcher.TiingoFetcher',
    },
    'histdata.com': {
        'classpath': 'watcher.connector.histdata.fetcher.HistDataFetcher',
    },
    'kraken.com': {
        'classpath': 'watcher.connector.kraken.fetcher.KrakenFetcher',
    },  
}

WATCHERS = {
    '1broker.com': {
        'status': 'load',
        'classpath': 'watcher.connector.onebroker.watcher.OneBrokerWatcher',
        # 'authors': [
        #     {
        #         'username': 'wangzai888',
        #         'id': '11531',
        #         'status': 'share',
        #         'instruments': ['forex', 'stock', 'commodity'],
        #         'confidence': [0, 0, 0, 5, 5, 5, 5, 3],
        #         'comments': ['blabla']
        #     },
        # ],
        'symbols': [],
    },
    'alphavantage.co': {
        'status': 'load',
        'classpath': 'watcher.connector.alphavantage.watcher.AlphaVantageWatcher',
        'symbols': ['*'],
    },
    'binance.com': {
        'status': 'load',
        'classpath': 'watcher.connector.binance.watcher.BinanceWatcher',
        'symbols': [],
        # 'symbols': ['*USDT', '*BTC'],
    },  
    'bitmex.com': {
        'status': 'load',
        'classpath': 'watcher.connector.bitmex.watcher.BitMexWatcher',
        'symbols': [],
        # 'symbols': ['XBTUSD', 'ETHUSD', 'LTCU19', 'TRXU19', 'EOSU19', 'XRPU19', 'ADAU19', 'BCHU19', 'XBTU19'],
    },
    'ig.com': {
        'status': 'load',
        'classpath': 'watcher.connector.ig.watcher.IGWatcher',
        'symbols': []  # https://labs.ig.com/sample-apps/api-companion/index.html
        # 'symbols': [
        #     'CS.D.AUDNZD.MINI.IP',
        #     'CS.D.EURCAD.MINI.IP',
        #     'CS.D.EURJPY.MINI.IP',
        #     'CS.D.EURUSD.MINI.IP',          
        #     'CS.D.GBPUSD.MINI.IP',
        #     'CS.D.USDJPY.MINI.IP',
        #     'CS.D.CFEGOLD.CFE.IP',  # Or au comptant (1€)
        #     'IX.D.SPTRD.IFE.IP',    # US 500 au comptant (1€)
        # ],
    },
    'kraken.com': {
        'status': 'load',
        'classpath': 'watcher.connector.kraken.watcher.KrakenWatcher',
        'symbols': [],
        # 'symbols': ['XXBTZUSD', 'XXBTZEUR', 'XETHZUSD', 'XETHZEUR', 'XXRPZUSD', 'XXRPZEUR'],
    },
    'tiingo.com': {
        'status': 'load',
        'classpath': 'watcher.connector.tiingo.watcher.TiingoWatcher',
        'symbols': [],
        # 'symbols': ['MSFT', 'GOOG', 'APPL', 'SPOT']
    },
    'tradingview.com': {
        'status': 'load',
        'classpath': 'watcher.connector.tradingview.watcher.TradingViewWatcher',
        'host': '127.0.0.1',
        'port': 7373,
        'symbols': [],
    },
}

TRADERS = {
    '1broker.com': {
        'status': 'load',
        'classpath': 'trader.connector.onebroker.trader.OneBrokerTrader',
        'leverages': {
            # manual leverage limits
            '(ANY)': [1, 100],
            'AUDNZD': [50, 100],
            'AUDUSD': [50, 100],
            'EURAUD': [75, 125],
            'EURCAD': [75, 125],
            'EURCHF': [75, 125],
            'EURCNH': [50, 100],
            'EURGBP': [75, 125],
            'EURJPY': [75, 100],
            'EURMXN': [50, 75],
            'EURTRY': [50, 100],
            'EURUSD': [75, 125],
            'GBPUSD': [75, 125],
            'USDAUD': [75, 125],
            'USDCAD': [75, 125],
            'USDCHN': [75, 125],
            'USDCNH': [50, 100],
            'USDMXN': [25, 50],
            'USDJPY': [75, 100],
            'USDTRY': [50, 100],
            'XAUUSD': [5, 15],
            'XAGUSD': [5, 15],
            'OILWTI': [5, 10],
            '(STOCKS)': [1, 15],
        },
        'symbols': [],
    },
    'binance.com': {
        'status': 'load',
        'classpath': 'trader.connector.binance.trader.BinanceTrader',
        'symbols': [],
        # 'symbols': ['*USDT', '*BTC'],
    },
    'bitmex.com': {
        'status': 'load',
        'classpath': 'trader.connector.bitmex.trader.BitMexTrader',
        'symbols': [],
        # 'symbols': ['XBTUSD', 'ETHUSD', 'LTCU19', 'TRXU19', 'EOSU19', 'XRPU19', 'ADAU19', 'BCHU19', 'XBTU19'],
    },
    'ig.com': {
        'status': 'load',
        'classpath': 'trader.connector.ig.trader.IGTrader',
        'symbols': [],
    #     'symbols': [
    #         'CS.D.AUDNZD.MINI.IP',
    #         'CS.D.AUDUSD.MINI.IP',
    #         'CS.D.EURCAD.MINI.IP',
    #         'CS.D.EURUSD.MINI.IP',
    #         'CS.D.EURJPY.MINI.IP',
    #         'CS.D.GBPUSD.MINI.IP',
    #         'CS.D.USDJPY.MINI.IP',
    #         'CS.D.CFEGOLD.CFE.IP',  # Or au comptant (1€)
    #         'IX.D.SPTRD.IFE.IP',    # US 500 au comptant (1€)
    #     ],
    },
    'kraken.com': {
        'status': 'load',
        'classpath': 'trader.connector.kraken.trader.KrakenTrader',
        'symbols': [],
        # 'symbols': ['XXBTZUSD', 'XXBTZEUR', 'XETHZUSD', 'XETHZEUR', 'XXRPZUSD', 'XXRPZEUR'],
    },
}

INDICATORS = {
    'price': {
        'status': 'load',
        'classpath': 'strategy.indicator.price.price.PriceIndicator',
        'options': {
        }
    },
    'volume': {
        'status': 'load',
        'classpath': 'strategy.indicator.volume.volume.VolumeIndicator',
        'options': {
        }
    },
    'rsi': {
        'status': 'load',
        'classpath': 'strategy.indicator.rsi.rsi.RSIIndicator',
        'options': {
        }
    },
    'stochrsi': {
        'status': 'load',
        'classpath': 'strategy.indicator.stochrsi.stochrsi.StochRSIIndicator',
        'options': {
        }
    },
    'stochastic': {
        'status': 'load',
        'classpath': 'strategy.indicator.stochastic.stochastic.StochasticIndicator',
        'options': {
        }
    },  
    'momentum': {
        'status': 'load',
        'classpath': 'strategy.indicator.momentum.momentum.MomentumIndicator',
        'options': {
        }
    },
    'macd': {
        'status': 'load',
        'classpath': 'strategy.indicator.macd.macd.MACDIndicator',
        'options': {
        }
    },
    'sma': {
        'status': 'load',
        'classpath': 'strategy.indicator.sma.sma.SMAIndicator',
        'options': {
        }
    },
    'ema': {
        'status': 'load',
        'classpath': 'strategy.indicator.ema.ema.EMAIndicator',
        'options': {
        }
    },
    'hma': {
        'status': 'load',
        'classpath': 'strategy.indicator.hma.hma.HMAIndicator',
        'options': {
        }
    },
    'wma': {
        'status': 'load',
        'classpath': 'strategy.indicator.wma.wma.WMAIndicator',
        'options': {
        }
    },
    'vwma': {
        'status': 'load',
        'classpath': 'strategy.indicator.vwma.vwma.VWMAIndicator',
        'options': {
        }
    },
    'bollingerbands': {
        'status': 'load',
        'classpath': 'strategy.indicator.bollingerbands.bollingerbands.BollingerBandsIndicator',
        'options': {
        }
    },
    'fibonacci': {
        'status': 'load',
        'classpath': 'strategy.indicator.fibonacci.fibonacci.FibonacciIndicator',
        'options': {
        }
    },
    'triangle': {
        'status': 'load',
        'classpath': 'strategy.indicator.triangle.triangle.TriangleIndicator',
        'options': {
        }
    },
    'pivotpoint': {
        'status': 'load',
        'classpath': 'strategy.indicator.pivotpoint.pivotpoint.PivotPointIndicator',
        'options': {
        }
    },
    'tomdemark': {
        'status': 'load',
        'classpath': 'strategy.indicator.tomdemark.tomdemark.TomDemarkIndicator',
        'options': {
        }
    },
    'atr': {
        'status': 'load',
        'classpath': 'strategy.indicator.atr.atr.ATRIndicator',
        'options': {
        }
    },
    'donchian': {
        'status': 'load',
        'classpath': 'strategy.indicator.donchian.donchian.DonchianIndicator',
        'options': {
        }
    },
    'sar': {
        'status': 'load',
        'classpath': 'strategy.indicator.sar.sar.SARIndicator',
        'options': {
        }
    },
    'history': {
        'status': 'load',
        'classpath': 'strategy.indicator.history.history.HistoryIndicator',
        'options': {
        }
    },
    'bbawe': {
        'status': 'load',
        'classpath': 'strategy.indicator.bbawe.bbawe.BBAweIndicator',
        'options': {
        }
    },
    'sinewave': {
        'status': 'load',
        'classpath': 'strategy.indicator.sinewave.sinewave.SineWaveIndicator',
        'options': {
        }
    },
    'zigzag': {
        'status': 'load',
        'classpath': 'strategy.indicator.zigzag.zigzag.ZigZagIndicator',
        'options': {
        }
    },
    'mama': {
        'status': 'load',
        'classpath': 'strategy.indicator.mama.mama.MAMAIndicator',
        'options': {
        }
    },
    'ichimoku': {
        'status': 'load',
        'classpath': 'strategy.indicator.ichimoku.ichimoku.IchimokuIndicator',
        'options': {
        }
    },
}

TRADEOPS = {
    'dynamic-stop-loss': {
        'status': 'load',
        'classpath': 'strategy.tradeop.tradeop.TradeOpDynamicStopLoss',
        'options': {
        }
    },
}

REGIONS = {
    'range': {
        'status': 'load',
        'classpath': 'strategy.region.region.RangeRegion',
        'options': {
        }
    },
    'trend': {
        'status': 'load',
        'classpath': 'strategy.region.region.TrendRegion',
        'options': {
        }
    },
}

STRATEGIES = {
    'boostedblueskyday': {
        'status': 'load',
        'classpath': 'strategy.boostedblueskyday.bbstrategy.BoostedBlueSkyDayStrategy',
        'options': {
        }
    },
    'socialcopy': {
        'status': 'load',
        'classpath': 'strategy.socialcopy.scstrategy.SocialCopyStrategy',
        'options': {
        }
    },
    'cryptoalpha': {
        'status': 'load',
        'classpath': 'strategy.cryptoalpha.castrategy.CryptoAlphaStrategy',
        'options': {
        }
    },
    'forexalpha': {
        'status': 'load',
        'classpath': 'strategy.forexalpha.fastrategy.ForexAlphaStrategy',
        'options': {
        }
    },
    'indicealpha': {
        'status': 'load',
        'classpath': 'strategy.indicealpha.iastrategy.IndiceAlphaStrategy',
        'options': {
        }
    },
    'bitcoinalpha': {
        'status': 'load',
        'classpath': 'strategy.bitcoinalpha.bcastrategy.BitcoinAlphaStrategy',
        'options': {
        }
    },
    'crystalball': {
        'status': 'load',
        'classpath': 'strategy.crystalball.cbstrategy.CrystalBallStrategy',
        'options': {
        }
    },
}

# For the monitoring connector interface
MONITORING = {
    'host': '127.0.0.1',      # listening host
    'port': 8080,             # and port
    'allowdeny': 'allowany',  # can be allowany, denyall, allowlist, denylist
    'list': None,             # allowed or blocked IPs
    'api-key': 'e4f7d47e832e115df640ec3b1c95a417c2f26286'  # replace with your generated unique key, using bash: date --rfc-3339=ns | sha1sum | awk '{print $1}'
}
