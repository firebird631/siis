# @date 2018-08-08
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Watcher, traders, indicator configuration

DATABASES = {
    'siis': {
        'type': 'pgsql',
        'user': 'siis',
        'password': 'siis',
        'host': '127.0.0.1',
        'port': 5432,
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
}

WATCHERS = {
    '1broker.com': {
        'status': None,  # 'load',
        'classpath': 'watcher.connector.onebroker.watcher.OneBrokerWatcher',
        'authors': [
            {
                'id': '11531',  # wangzai888
                'status': 'share',
                'instruments': ['forex', 'stock', 'commodity'],
                'confidence': [0, 0, 0, 5, 5, 5, 5, 3],
                'comments': ['rare trades a bit risky but often good results, must be patient, and good over the time', '2x-80% on gold on half of august']
            },
        ],
        'symbols': []  # @todo for watching using WS
    },
    '1fox.com': {
        'status': None,
        'classpath': 'watcher.connector.onebroker.watcher.OneFoxWatcher',
        'authors': [],
        'symbols': ['BTCUSD', 'BCHUSD']
    },
    'alphavantage.co': {
        'status': 'load',
        'classpath': 'watcher.connector.alphavantage.watcher.AlphaVantageWatcher',
        'symbols': ['*']
    },
    'binance.com': {
        'status': 'load',
        'classpath': 'watcher.connector.binance.watcher.BinanceWatcher',
        'symbols': ['*USDT', '*BTC'],
    },  
    'bitmex.com': {
        'status': 'load',
        'classpath': 'watcher.connector.bitmex.watcher.BitMexWatcher',
        'symbols': ['XBTUSD', 'ETHUSD', 'LTCH19', 'TRXH19', 'EOSH19', 'XRPH19', 'ADAH19', 'BCHH19', 'XBTH19'],
    },
    'ig.com': {
        'status': 'load',
        'classpath': 'watcher.connector.ig.watcher.IGWatcher',
        'symbols': [  # https://labs.ig.com/sample-apps/api-companion/index.html
            'CS.D.AUDNZD.MINI.IP',
            'CS.D.EURCAD.MINI.IP',
            'CS.D.EURJPY.MINI.IP',
            'CS.D.EURUSD.MINI.IP',          
            'CS.D.GBPUSD.MINI.IP',
            'CS.D.USDJPY.MINI.IP',
            'CS.D.CFEGOLD.CFE.IP',  # Or au comptant (1€)
            'IX.D.SPTRD.IFE.IP',    # US 500 au comptant (1€)
        ],
    },
    'tiingo.com': {
        'status': None,  # 'load',
        'classpath': 'watcher.connector.tiingo.watcher.TiingoWatcher',
        'symbols': ['MSFT', 'GOOG', 'APPL', 'SPOT', 'EDF']  # ...
    },
    'tradingview.com': {
        'status': None,  # 'load',
        'classpath': 'watcher.connector.tradingview.watcher.TradingViewWatcher',
        'host': '127.0.0.1',
        'port': 7373,
    },
}

TRADERS = {
    '1broker.com': {
        'status': None,  # 'load',
        'classpath': 'trader.connector.onebroker.trader.OneBrokerTrader',
        'leverage': {  # @deprecated defined into the appliance/instruments, and its different if using social strategy
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
        'stop-loosing-position': {
            'mode': 'percent',  # level in account currency or percent of position cost
            'value': 0.4        # when reach loss of 40% auto-close the position
        }       
    },
    '1fox.com': {
        'status': None,  # 'load', @todo api are not same version as 1broker.com
        'classpath': 'trader.connector.onefox.trader.OneFoxTrader',
        'symbols': ['BTCUSD', 'BCHUSD'],
        'stop-loosing-position': {
            'mode': 'percent',
            'value': 0.4
        }
    },
    'binance.com': {
        'status': 'load',
        'classpath': 'trader.connector.binance.trader.BinanceTrader',
        'symbols': ['*USDT', '*BTC'],
        'paper-mode': {
            'type': 'asset',
            'currency': 'BTC',
            'currency-symbol': 'BTC',
            'alt-currency': 'USDT',
            'alt-currency-symbol': 'USDT',
            'initial': 0.1,  # in currency in quote
            'price': 3450
        },
        'stop-loosing-position': {
            'mode': 'percent',
            'value': 0.4
        }
    },
    'bitmex.com': {
        'status': 'load',
        'classpath': 'trader.connector.bitmex.trader.BitMexTrader',
        'symbols': ['XBTUSD', 'ETHUSD', 'LTCH19', 'TRXH19', 'EOSH19', 'XRPH19', 'ADAH19', 'BCHH19', 'XBTH19'],  # , 'XBTH19'],
        'paper-mode': {
            'currency': 'BTC',
            'currency-symbol': 'BTC',
            'initial': 0.1,
        },
        'stop-loosing-position': {
            'mode': 'percent',
            'value': 0.4        # when reach loss of 40% auto-close the position
        }
    },
    'ig.com': {
        'status': 'load',
        'classpath': 'trader.connector.ig.trader.IGTrader',
        'symbols': [
            'CS.D.AUDNZD.MINI.IP',
            'CS.D.AUDUSD.MINI.IP',
            'CS.D.EURCAD.MINI.IP',
            'CS.D.EURUSD.MINI.IP',
            'CS.D.EURJPY.MINI.IP',
            'CS.D.GBPUSD.MINI.IP',
            'CS.D.USDJPY.MINI.IP',
            'CS.D.CFEGOLD.CFE.IP',  # Or au comptant (1€)
            'IX.D.SPTRD.IFE.IP',    # US 500 au comptant (1€)
        ],
        'paper-mode': {
            'currency': 'USD',
            'currency-symbol': '$',
            'initial': 1000,
        }, 
        'stop-loosing-position': {
            'mode': 'percent',
            'value': 0.4        # when reach loss of 40% auto-close the position
        }
    }
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
}

TRADEOPS = {
    'dynamic-stop-loss': {
        'status': 'load',
        'classpath': 'strategy.tradeop.tradeop.TradeOpDynamicStopLoss',
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

MONITORING = {
    'allowdeny': 'allowany',  # can be allowany, denyall, allowlist, denylist
    'allowlist': None,
    'api-key': 'dadadidadada'
}
