# @date 2018-08-08
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Appliances configuration

# This file serves as template purpose only. Put your into your siis config directory.

SIZE_FACTOR = 1.0  # @todo could be a factor configured at the identity level

PROFILES = {
	'default': {'appliances': ['*'], 'traders': ['*']}
}

APPLIANCES = {
	'binance-altusdt': {
		'status': 'enabled',
		'strategy': {
			'name': 'cryptoalpha',
			'options': {
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
					'quote': 'USDT',  # define the quote asset to use (default uses account balance)
					'size': 250,      # in quote asset (to be divided by the asset price in quote)
				},
			}
		}
	},
	'binance-altbtc': {
		'status': 'enabled',
		'strategy': {
			'name': 'cryptoalpha',
			'options': {
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
					'quote': 'BTC',  # define the quote asset to use (default uses account balance)
					'size': 0.05,    # in quote asset (to be divided by the asset price in quote)
					'stop-loss': {
						'mode': 'market',
						'distance': 20,
						'trailing': {
							'status': True,
							'distance': 5
						}
					},
					'take-profit': {
						'mode': 'limit',
						'distance': 30
					}
				},
			}
		}
	},
	'bitmex-xbtusd-ethusd': {
		'status': 'disabled',  # 'enabled',
		'strategy': {
			'name': 'cryptoalpha',
			'options': {
				'policy': 'auto',    # can be manual or auto
				'mode': 'reversal',  # can mode entryexit or reversal
				'timeframe': 60,
				'deep': 48,
				'resolution': 60
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
					'size': 1000*SIZE_FACTOR,    # USD
					'stop-loss': {
						'mode': 'market',
						'distance': 100,  # defines a security stop loss at -100$
						'trailing': {  # @todo what exactly we want
							'status': True,  # and it is a trailing stop a 50$ distance
							'distance': 50
						}
					},
					'take-profit': {
						'mode': 'limit',
						'distance': 150  # defines a max take profit a 150$
					}
				},
				'ETHUSD': {
					'market-id': 'ETHUSD',
					'size': 1000*SIZE_FACTOR,    # USD
					'stop-loss': {
						'mode': 'market',
						'distance': 30,  # defines a security stop loss at -30$
						'trailing': {  # @todo what exactly we want
							'status': True,  # and it is a trailing stop a 50$ distance
							'distance': 30
						}
					},
					'take-profit': {
						'mode': 'limit',
						'distance': 30  # defines a max take profit at 30$
					}
				}
			}
		}
	},
	'bitmex-alts': {
		'status': 'disabled',
		'strategy': {
			'name': 'cryptoalpha',
			'options': {  # @todo in limit order !!
				'policy': 'auto',    # can be manual or auto
				'mode': 'reversal',  # can mode entryexit or reversal
				'timeframe': 60,
				'deep': 48,
				'resolution': 60
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
					'size': 1000*SIZE_FACTOR,    # XRP contracts
					'stop-loss': {
						'mode': 'market',
						'distance': 100,  # defines a security stop loss at -100$
						'trailing': {  # @todo what exactly we want
							'status': True,  # and it is a trailing stop a 50$ distance
							'distance': 50
						}
					},
					'take-profit': {
						'mode': 'limit',
						'distance': 150  # defines a max take profit a 150$
					}
				},
				'TRXZ18': {
					'market-id': 'TRXZ18',
					'size': 50000*SIZE_FACTOR,    # TRX contracts
					'stop-loss': {
						'mode': 'market',
						'distance': 100,
						'trailing': {
							'status': True,
							'distance': 50
						}
					},
					'take-profit': {
						'mode': 'limit',
						'distance': 150  # defines a max take profit a 150$
					}
				},
			}
		}
	},
	'ig-forex-mini': {
		'status': 'enabled',
		'strategy': {
			'name': 'forexalpha',
			'options': {  # @todo see DEFAULT_PARAMS thoose are not applyed
				'policy': 'auto',
				'mode': 'reversal',
				'timeframe': 60,
				'deep': 120,
				'resolution': 30*60
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
					'size': 1.0*SIZE_FACTOR,
					'value-per-pip': 1.0,
					'contract-size': 10000,
					'lot-size': 1.0,
					'currency': 'NZD',
					'one-pip-means': 0.0001,
					'take-profit': {
						'mode': 'market',
						'distance': 50
					},
					'stop-loss': {
						'mode': 'normal',
						'distance': 20
					}
				},
				'EURCAD': {
					'market-id': 'CS.D.EURCAD.MINI.IP',
					'leverage': 30.0,  # account and fixed for forex
					'size': 1.0*SIZE_FACTOR,
					'value-per-pip': 1.0,
					'contract-size': 10000,
					'lot-size': 1.0,
					'currency': 'CAD',
					'one-pip-means': 0.0001,
					'take-profit': {
						'mode': 'market',
						'distance': 50
					},
					'stop-loss': {
						'mode': 'normal',
						'distance': 20
					}
				},
				'EURJPY': {
					'market-id': 'CS.D.EURJPY.MINI.IP',
					'leverage': 30.0,  # account and fixed for forex
					'size': 1.0*SIZE_FACTOR,
					'value-per-pip': 50.0,
					'contract-size': 10000,
					'lot-size': 100.0,
					'currency': 'JPY',
					'one-pip-means': 0.01,
					'take-profit': {
						'mode': 'market',
						'distance': 50
					},
					'stop-loss': {
						'mode': 'normal',
						'distance': 20
					}
				},
				'EURUSD': {
					'market-id': 'CS.D.EURUSD.MINI.IP',
					'leverage': 30.0,  # account and fixed for forex
					'size': 1.0*SIZE_FACTOR,
					'value-per-pip': 1.0,
					'contract-size': 10000,
					'lot-size': 0.5,
					'currency': 'USD',
					'one-pip-means': 0.0001,
					'take-profit': {
						'mode': 'market',
						'distance': 50
					},
					'stop-loss': {
						'mode': 'normal',
						'distance': 20
					}
				},
				'GBPUSD': {
					'market-id': 'CS.D.GBPUSD.MINI.IP',
					'leverage': 30.0,  # account and fixed for forex
					'size': 1.0*SIZE_FACTOR,
					'value-per-pip': 1.0,
					'contract-size': 10000,
					'lot-size': 1.0,
					'currency': 'USD',
					'one-pip-means': 0.0001,
					'take-profit': {
						'mode': 'market',
						'distance': 50
					},
					'stop-loss': {
						'mode': 'normal',
						'distance': 20
					}
				},
				'USDJPY': {
					'market-id': 'CS.D.USDJPY.MINI.IP',
					'leverage': 30.0,  # account and fixed for forex
					'size': 1.0*SIZE_FACTOR,
					'value-per-pip': 50,
					'contract-size': 10000,
					'lot-size': 100.0,
					'currency': 'JPY',
					'one-pip-means': 0.01,
					'take-profit': {
						'mode': 'market',
						'distance': 50
					},
					'stop-loss': {
						'mode': 'normal',
						'distance': 20
					}
				},
			}
		}
	},
	'ig-indice-mini': {
		'status': 'disabled',
		'strategy': {
			'name': 'indicealpha',
			'options': {
				'policy': 'auto',
				'mode': 'reversal',
				'timeframe': 60,
				'deep': 120,
				'resolution': 30*60
			},
		},
		'watcher': [{
			'name': 'ig.com',
			'symbols': ['IX.D.SPTRD.IFE.IP']  # @todo add DAX30, NIKEY, HK50, CAC40
		}],
		'trader': {
			'name': 'ig.com',
			'instruments': {
				'SPX500': {
					'market-id': 'IX.D.SPTRD.IFE.IP',
					'leverage': 20,  # account and fixed for forex
					'size': 1.0*SIZE_FACTOR,
					'value-per-pip': 1.0,
					'contract-size': 1.0,
					'lot-size': 1,
					'currency': 'EUR',
					'one-pip-means': 1.0,
					'take-profit': {
						'mode': 'market',
						'distance': 50
					},
					'stop-loss': {
						'mode': 'normal',
						'distance': 20
					}
				},
			}
		}
	},
	'ig-commodity-mini': {
		'status': 'disabled',
		'strategy': {
			'name': 'forexalpha',
			'options': {
				'policy': 'auto',
				'mode': 'reversal',
				'timeframe': 60,
				'deep': 120,
				'resolution': 30*60
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
					'size': 1.0*SIZE_FACTOR,
					'value-per-pip': 1.0,
					'contract-size': 1.0,
					'lot-size': 1.0,
					'currency': 'USD',
					'one-pip-means': 1.0,
					'take-profit': {
						'mode': 'market',
						'distance': 50
					},
					'stop-loss': {
						'mode': 'normal',
						'distance': 20
					}
				},
			}
		}
	},
	'1broker-forex': {
		# Any forex social copy signal manual entry, auto exit copy
		'status': 'disabled',
		'strategy': {
			'name': 'socialcopy',
			'options': {
				'entry': 'manual',  # can be manual or auto
				'exit': 'auto'
			}
		},
		'watcher': [{
			'name': '1broker.com',
			'symbols': ['(FOREX)'],   # only filter forex
			'options:': {
				'authors': None  # !! mean follow any authors configured into the watcher, else define a list of ids
			}
		}],
		# @todo mapping with category name... or force to list any
		'trader': {
			'name': '1broker.com',
			'instruments': {
				'(MAJORS-FOREX)': {   # map any major forex, using theese settings, some others need different size/leverage
					'market-id': None,       # no mapping is necessary because the symbols are the sames
					'size': 0.002*SIZE_FACTOR,    # BTC
					'leverage': {
						'min': 1,     # minimal leverage
						'max': 100    # maximal leverage
					},
					'stop-loss': {
						'mode': 'market',
						'value': 'percent',
						'distance': 50  # defines a security stop loss at 50%
					},
					'take-profit': {
						'mode': 'limit',
						'value': 'percent',
						'distance': 50  # defines a reward at 50%
					}
				}
			}
		}
	},
}
