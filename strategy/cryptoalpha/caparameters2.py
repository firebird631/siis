# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy default parameters.

# magic 8,13,21,55,89,13
DEFAULT_PARAMS = {
    'reversal': True,
    'max-trades': 1,    # max number of simultaned trades for a same market
    'trade-delay': 30,  # at least wait 30 seconds before sending another signal 
    'base-timeframe': 't',   # process each time strategy receive a tick
    'min-traded-timeframe': '1m',
    'max-traded-timeframe': '1m',
    'sltp-timeframe': '1h',
    'ref-timeframe': '4h',
    'need-update': True,      # only compute when update is waited
    'min-vol24h': 100,        # 100 BTC per 24h
    'min-price': 0.00000069,  # or 69 sats
    'region-allow': True,     # can trade if no defined region
    'timeframes': {
        '4hour': {
            'timeframe': '4h',
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
            'parent': '4h',
            'mode': 'B', 
            'depth': 22,
            'history': 22,
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
                'bollingerbands': ('bollingerbands', 20,),
                'triangle': None,
                'pivotpoint': ('pivotpoint', 0,),
                'atr': ('atr', 21, 3.5),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        },
        '30min': {
            'timeframe': '30m',
            'parent': '1h',
            'mode': 'B',
            'depth': 22,
            'history': 22,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'volume_ema': ('ema', 8,),
                'rsi': ('rsi', 14,),
                'sma': ('sma', 20,),
                'ema': ('ema', 8,),
                'hma': None,
                'vwma': ('vwma', 21,),
                'momentum': ('momentum', 21,),
                'stochastic': None,
                'macd': None,  # ('macd', 21,),
                'bollingerbands': ('bollingerbands', 14,),
                'triangle': None,
                'pivotpoint': ('pivotpoint', 0,),
                'tomdemark': ('tomdemark', 9),
                'atr': ('atr', 14, 3.0),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        },
        '1min': {
            'timeframe': '1m',
            'parent': '30m',
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
