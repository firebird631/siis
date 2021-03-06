# @date 2019-01-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Crystal ball strategy default parameters.

DEFAULT_PARAMS = {
    "reversal": True,
    "pyramided": 0,
    "hedging": False,
    "max-trades": 3,    # max number of simultaneous trades for a same market
    "trade-delay": 30,  # at least wait 30 seconds before sending another signal 
    "min-traded-timeframe": "1m",
    "max-traded-timeframe": "4h",
    "min-vol24h": 100,        # 300 BTC per 24h
    "min-price": 0.00000069,  # or 69 sats (to binary otherwise)
    "timeframes": {
        "4hour": {
            "timeframe": "4h",
            "mode": "A",
            "depth": 22,
            "history": 22,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 2,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 21,),
                "pivotpoint": ("pivotpoint", 5,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 1.0),  # was 1.5 , but too large else
                "bsawe": ("bsawe", 20, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            }   
        },
        "hourly": {
            "timeframe": "1h",
            "mode": "A", 
            "depth": 22,
            "history": 22,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 2,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 21,),
                "pivotpoint": ("pivotpoint", 5,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 1.0),  # was 1.5 , but too large else
                "bsawe": ("bsawe", 20, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            }
        },
        "15min": {
            "timeframe": "15m",
            "mode": "A",
            "depth": 22,
            "history": 22,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 2,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 21,),
                "pivotpoint": ("pivotpoint", 5,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 1.0),
                "bsawe": ("bsawe", 20, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            }
        },
        "5min": {
            "timeframe": "5m",
            "mode": "A",
            "depth": 22,
            "history": 22,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 2,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 21,),
                "pivotpoint": ("pivotpoint", 5,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 3.0),
                "bsawe": ("bsawe", 20, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            }
        },
        "2min":{
            "timeframe": "2m",
            "mode": "A",
            "depth": 22,
            "history": 22,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 2,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 21,),
                "pivotpoint": ("pivotpoint", 5,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 3.0),
                "bsawe": ("bsawe", 20, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            }
        },
        "1min": {
            "timeframe": "1m",
            "mode": "A",
            "depth": 22,
            "history": 22,
            "update-at-close": True,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 2,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 21,),
                "pivotpoint": ("pivotpoint", 5,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 3.0),
                "bsawe": ("bsawe", 20, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            }
        }
    }
}
