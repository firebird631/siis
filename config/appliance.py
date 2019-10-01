# @date 2018-08-08
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Appliances configuration

# This file serves as template purpose only. Put your into your siis config directory.

PROFILES = {
    'default': {
        # default or not specified profile, we want nothing loaded
        'appliances': [],
        'watchers':  {},
        'traders': {}
    },

    'binance-all': {
        # example of profile starting two appliance on the same account
        'appliances': ['binance-altbtc', 'binance-baseusdt'],
        'watchers':  {
            'binance.com': {
                # enable the binance connector and watcher, needed to get price data, order book
                # and necessary for the binance trader works in live
                'status': 'enabled'
            }
        },
        'traders': {
            'binance.com': {
                # want a binance trader (need to have to binance watcher at least)
                'paper-mode': {
                    # if started in paper-mode it defines two assets quantities (USDT and BTC)
                    'type': 'asset',
                    'currency': 'BTC',  # primary account currency, always BTC for binance
                    'currency-symbol': '₿',
                    'alt-currency': 'USDT',   # secondary account currency, one of the USD(s)
                    'alt-currency-symbol': 'Ť',
                    'assets': [{
                        'base': 'USDT',
                        'quote': 'USDT',
                        'initial': 10000.0
                    }, {
                        'base': 'BTC',
                        'quote': 'USDT',
                        'initial': 10.0
                    }]
                }
            }
        }
    },
      
    'binance-signal': {
        # pure signals no trading
        'appliances': ['binance-signal'],
        'watchers':  {
            'binance.com': {
                'status': 'enabled'
            },
        },
        'traders': {
            'binance.com': {
                'status': 'enabled'
            }
        }
    },       
}

APPLIANCES = {
    'binance-baseusdt': {
        'status': 'enabled',
        'strategy': {
            'name': 'cryptoalpha',
            'parameters': {
            }
        },
        'watcher': [{
            'name': 'binance.com',
            'symbols': ['*USDT'],
        }],
        'trader': {
            'name': 'binance.com',
            'instruments': {
                '*USDT': {
                    'market-id': '{0}',
                    'size': 250
                },
            }
        }
    },
    'binance-altbtc': {
        'status': 'enabled',
        'strategy': {
            'name': 'cryptoalpha',
            'parameters': {
            }
        },
        'watcher': [{
            'name': 'binance.com',
            'symbols': ['*BTC'],
        }],
        'trader': {
            'name': 'binance.com',
            'instruments': {
                '*BTC': {
                    'market-id': '{0}',
                    'size': 0.05
                },
            }
        }
    },
    'bitmex-xbtusd-ethusd': {
        'status': 'disabled',
        'strategy': {
            'name': 'cryptoalpha',
            'parameters': {
            },
        },
        'watcher': [{
            'name': 'bitmex.com',
            'symbols': ['XBTUSD', 'ETHUSD']
        }],
        'trader': {
            'name': 'bitmex.com',
            'instruments': {
                'XBTUSD': {
                    'market-id': 'XBTUSD',  # means map BTCUSD to XTBUSD (perpetual contract)
                    'size': 1000,
                },
                'ETHUSD': {
                    'market-id': 'ETHUSD',
                    'size': 1000,
                }
            }
        }
    },
    'bitmex-alts': {
        'status': 'disabled',
        'strategy': {
            'name': 'cryptoalpha',
            'parameters': {
            },
        },
        'watcher': [{
            'name': 'bitmex.com',
            'symbols': ['XRPZ18', 'TRXZ18']
        }],
        'trader': {
            'name': 'bitmex.com',
            'instruments': {
                'XRPZ18': {
                    'market-id': 'XRPZ18',
                    'size': 1000,
                },
                'TRXZ18': {
                    'market-id': 'TRXZ18',
                    'size': 50000,
                },
            }
        }
    },
    'ig-forex-mini': {
        'status': 'enabled',
        'strategy': {
            'name': 'forexalpha',
            'parameters': {
            },
        },
        'watcher': [{
            'name': 'ig.com',
            'symbols': [
                # 'CS.D.AUDNZD.MINI.IP',
                'CS.D.EURUSD.MINI.IP',
                # 'CS.D.EURJPY.MINI.IP',
                # 'CS.D.GBPUSD.MINI.IP',
                'CS.D.USDJPY.MINI.IP',
                'CS.D.EURCAD.MINI.IP',
            ]
        }],
        'trader': {
            'name': 'ig.com',
            'instruments': {
                'AUDNZD': {
                    'market-id': 'CS.D.AUDNZD.MINI.IP',
                    'leverage': 30.0,  # account and fixed for forex
                    'size': 1.0,
                    # 'value-per-pip': 1.0,
                    # 'contract-size': 10000,
                    # 'lot-size': 1.0,
                    # 'currency': 'NZD',
                    # 'one-pip-means': 0.0001,
                },
                'EURCAD': {
                    'market-id': 'CS.D.EURCAD.MINI.IP',
                    'leverage': 30.0,  # account and fixed for forex
                    'size': 1.0,
                    # 'value-per-pip': 1.0,
                    # 'contract-size': 10000,
                    # 'lot-size': 1.0,
                    # 'currency': 'CAD',
                    # 'one-pip-means': 0.0001,
                },
                'EURJPY': {
                    'market-id': 'CS.D.EURJPY.MINI.IP',
                    'leverage': 30.0,  # account and fixed for forex
                    'size': 1.0,
                    # 'value-per-pip': 50.0,
                    # 'contract-size': 10000,
                    # 'lot-size': 100.0,
                    # 'currency': 'JPY',
                    # 'one-pip-means': 0.01,
                },
                'EURUSD': {
                    'market-id': 'CS.D.EURUSD.MINI.IP',
                    'leverage': 30.0,  # account and fixed for forex
                    'size': 1.0,
                    # 'value-per-pip': 1.0,
                    # 'contract-size': 10000,
                    # 'lot-size': 0.5,
                    # 'currency': 'USD',
                    # 'one-pip-means': 0.0001,
                },
                'GBPUSD': {
                    'market-id': 'CS.D.GBPUSD.MINI.IP',
                    'leverage': 30.0,  # account and fixed for forex
                    'size': 1.0,
                    # 'value-per-pip': 1.0,
                    # 'contract-size': 10000,
                    # 'lot-size': 1.0,
                    # 'currency': 'USD',
                    # 'one-pip-means': 0.0001,
                },
                'USDJPY': {
                    'market-id': 'CS.D.USDJPY.MINI.IP',
                    'leverage': 30.0,  # account and fixed for forex
                    'size': 1.0,
                    # 'value-per-pip': 50,
                    # 'contract-size': 10000,
                    # 'lot-size': 100.0,
                    # 'currency': 'JPY',
                    # 'one-pip-means': 0.01,
                },
            }
        }
    },
    'ig-indice-mini': {
        'status': 'disabled',
        'strategy': {
            'name': 'indicealpha',
            'parameters': {
            },
        },
        'watcher': [{
            'name': 'ig.com',
            'symbols': ['IX.D.SPTRD.IFE.IP']
        }],
        'trader': {
            'name': 'ig.com',
            'instruments': {
                'SPX500': {
                    'market-id': 'IX.D.SPTRD.IFE.IP',
                    'leverage': 20,  # account and fixed for forex
                    'size': 1.0,
                    # 'value-per-pip': 1.0,
                    # 'contract-size': 1.0,
                    # 'lot-size': 1,
                    # 'currency': 'EUR',
                    # 'one-pip-means': 1.0,
                },
            }
        }
    },
    'ig-commodity-mini': {
        'status': 'disabled',
        'strategy': {
            'name': 'forexalpha',
            'parameters': {
                'reversal': False,
                'pyramided': 0,
                'hedging': True,
                'max-trades': 3,    # max number of simultaned trades for a same market
                'min-traded-timeframe': "1m",
                'max-traded-timeframe': "15m"
            },
        },
        'watcher': [{
            'name': 'ig.com',
            'symbols': ['CS.D.CFEGOLD.CFE.IP',]
        }],
        'trader': {
            'name': 'ig.com',
            'instruments': {
                'XAUUSD': {
                    'market-id': 'CS.D.CFEGOLD.CFE.IP',
                    'leverage': 30,  # account and fixed for forex
                    'size': 1.0,
                    # 'value-per-pip': 1.0,
                    # 'contract-size': 1.0,
                    # 'lot-size': 1.0,
                    # 'currency': 'USD',
                    # 'one-pip-means': 1.0,
                },
            }
        }
    },

    'binance-signal': {
        # this appliance will only notify of signal, but never trade, but it can manage manual trade
        'status': 'enabled',
        'strategy': {
            'name': 'crystalball',
            'parameters': {
                'min-traded-timeframe': "15m",
                'max-traded-timeframe': "1h"
            }
        },
        'watcher': [{
            'name': 'binance.com',
            'symbols': ['BTCUSDT', 'ETHBTC', 'XRPBTC', 'EOSBTC', 'LTCBTC', 'BCHABCBTC', 'ADABTC', 'XLMBTC',
                'TRXBTC', 'BCHSVBTC', 'DASHBTC', 'XMRBTC', 'ONTBTC', 'MIOTABTC', 'ATOMBTC', 'NEOBTC',
                'BNBBTC', 'IOSTBTC', 'ICXBTC', 'XLMBTC', 'ETCBTC','QTUMBTC', 'ZILBTC',
                'ETHUSDT', 'XRPUSDT', 'EOSUSDT', 'LTCUSDT', 'BCHABCUSDT', 'ADAUSDT', 'BCHSVUSDT', 'IOTAUSDT',
                'XLMUSDT', 'TRXUSDT', 'XMRUSDT', 'NEOUSDT', 'ETCUSDT', 'DASHUSDT', 'ZILUSDT'],
        }],
        'trader': {
            'name': 'binance.com',
            'instruments': {
                '*BTC': {
                    'market-id': '{0}',
                    'size': 0.02,
                },
                '*USDT': {
                    'market-id': '{0}',
                    'size': 100,
                }
            }
        }
    },
    '1broker-forex': {
        'status': 'disabled',
        'strategy': {
            'name': 'socialcopy',
            'parameters': {
                'entry': 'manual',  # can be manual or auto
                'exit': 'auto'
            }
        },
        'watcher': [{
            'name': '1broker.com',
            'symbols': ['(FOREX)'],   # only filter forex
            'parameters:': {
                'authors': None  # !! mean follow any authors configured into the watcher, else define a list of ids
            }
        }],
        'trader': {
            'name': '1broker.com',
            'instruments': {
                '(MAJORS-FOREX)': {   # map any major forex, using theese settings, some others need different size/leverage
                    'market-id': None,       # no mapping is necessary because the symbols are the sames
                    'size': 0.002,    # BTC
                    'leverage': {
                        'min': 1,     # minimal leverage
                        'max': 100    # maximal leverage
                    }
                }
            }
        }
    }
}
