# @date 2019-01-19
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Bitcoin Alpha strategy default parameters.

DEFAULT_PARAMS = {
    'reversal': True,
    'pyramided': 0,
    'hedging': False,
    'max-trades': 1,    # max number of simultaned trades for a same market
    'trade-delay': 30,  # at least wait 30 seconds before sending another signal 
    'base-timeframe': 't',   # process each time strategy receive a tick
    'min-traded-timeframe': '3m',
    'max-traded-timeframe': '3m',
    'sltp-timeframe': '1h',
    'ref-timeframe': '1d', # '4h',
    'need-update': True,      # only compute when update is waited
    'min-vol24h': 1000,       # 1000 BTC per 24h
    'min-price': 0.00000500,  # or 500 sats
    'region-allow': False,    # can trade if no defined regions
    'timeframes': {
        'daily': {
            'timeframe': '1d',
            'parent': None,
            'mode': 'B',
            'depth': 56,
            'history': 56,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'volume_ema': ('ema', 8,),
                'rsi': ('rsi', 21,),
                'stochrsi': ('stochrsi', 13, 13, 13),
                'sma200': None,
                'sma55': ('sma', 55,),
                'sma': ('sma', 50,),
                'ema': ('ema', 20,),
                'hma': None,
                'vwma': ('vwma', 21,),
                'momentum': ('momentum', 21,),
                'stochastic': None,
                'macd': None,  # ('macd', 21,),
                'triangle': None,
                'pivotpoint': ('pivotpoint', 5,),
                'tomdemark': ('tomdemark', 9),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }   
        },
        'hourly': {
            'timeframe': '1h',
            'parent': '1d',
            'mode': 'B', 
            'depth': 64,
            'history': 64,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'volume_ema': ('ema', 8,),
                'rsi': ('rsi', 9,),
                'stochrsi': ('stochrsi', 13, 13, 13),
                'sma200': None,
                'sma55': None,
                'sma': ('sma', 20,),
                'ema': ('ema', 8,),
                'hma': None,
                'vwma': ('vwma', 21,),
                'momentum': ('momentum', 21,),
                'stochastic': None,
                'macd': None,  # ('macd', 21,),
                # 'bollingerbands': ('bollingerbands', 20,),
                'triangle': None,
                'pivotpoint': ('pivotpoint', 0,),
                'atr': ('atr', 14, 1.5),
                'tomdemark': ('tomdemark', 9),
                'mama': ('mama', 0.5, 0.05),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        },
        # '30min': {
        #     'timeframe': '30m',
        #     'parent': '1h',
        #     'mode': 'B',
        #     'depth': 22,
        #     'history': 22,
        #     'indicators': {
        #         'price': ('price', 1,),
        #         'volume': ('volume', 0,),
        #         'volume_ema': ('ema', 8,),
        #         'rsi': ('rsi', 14,),
        #         'sma': ('sma', 20,),
        #         'ema': ('ema', 8,),
        #         'hma': None,
        #         'vwma': ('vwma', 21,),
        #         'momentum': ('momentum', 21,),
        #         'stochastic': None,
        #         'macd': None,  # ('macd', 21,),
        #         'bollingerbands': ('bollingerbands', 14,),
        #         'triangle': None,
        #         'pivotpoint': ('pivotpoint', 0,),
        #         'tomdemark': ('tomdemark', 9),
        #         'atr': ('atr', 14, 2.5),
        #         'mama': ('mama', 0.5, 0.05),
        #     },
        #     'constants': {
        #         'rsi_low': 0.3,
        #         'rsi_high': 0.7,
        #     }
        # },
        '3min': {
            'timeframe': '3m',
            'parent': '1h',  # '30m',
            'mode': 'A',
            'depth': 36,
            'history': 36,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'rsi': ('rsi', 14,),
                'stochrsi': None,
                'sma': ('sma', 20,),
                'ema': ('ema', 8,),
                'hma': ('hma', 8,),
                'vwma': ('vwma', 8,),
                'macd': None,  # ('macd', 17,),
                'bollingerbands': None, # ('bollingerbands', 26,),
                'triangle': None,
                'tomdemark': ('tomdemark', 9),
                'atr': ('atr', 14, 3.0),
                # 'bbawe': ('bbawe', 20, 2.0, 3.0, 5, 34, False),
                'bbawe': ('bbawe', 9, 2.0, 3.0, 5, 16, False),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        }
    }
}
