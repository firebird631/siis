# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Forex Alpha strategy default parameters

DEFAULT_PARAMS = {
    "reversal": True,
    "pyramided": 0,
    "hedging": True,
    "max-trades": 1,    # max number of simultaned trades for a same market
    "trade-delay": 30,  # at least wait 30 seconds before sending another signal 
    "score-trigger": 0.5,
    "score-increase-factor": 0.4,
    "score-regression-factor": 0.3,
    "min-traded-timeframe": "1m",
    "max-traded-timeframe": "1m",
    "min-vol24h": 100,        # 300 BTC per 24h
    "min-price": 0.00000069,  # or 69 sats (to binary otherwise)
    "timeframes": {
        "weekly": {
            "timeframe": "1w",
            "mode": "C",
            "depth": 22,
            "history": 22,
            "score-ratio": 8,
            "score-level": 0.05,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "volume_ema": ("ema", 8,),
                "rsi": ("rsi", 21,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 20,),
                "ema": ("ema", 21,),
                "hma": None,
                "vwma": ("vwma", 21,),
                "momentum": ("momentum", 21,),
                "stochastic": None,
                "macd": None,  # ("macd", 21,),
                "bollingerbands": ("bollingerbands", 36,),
                "triangle": None,
                "pivotpoint": ("pivotpoint", 0,),
                "tomdemark": None,
                "atr": ("atr", 14, 1.5),
                "bbawe": ("bbawe", 20, 2.0, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 0.3,
                "rsi_high": 0.7,
            },
            "scores": {
                "rsi_factor": 1.0,
                "rsi_trend_factor": 0.5,
                "sma_ema_cross_factor": (-0.5, -0.5),  # no-div/div
                "ema_vwma_cross_factor": (-5, -5),
                "price_vwma_factor": 50.0,
                "ema_vwma_cross_bonus": 0,  # 1,2,3,5
                "rsi_ema_trend_div_factor": (-0.04, -0.04),
            },
        },
        "daily": {
            "timeframe": "1d",
            "mode": "A",
            "depth": 41,
            "history": 41,
            "score-ratio": 4,
            "score-level": 0.05,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "volume_ema": ("ema", 8,),
                "rsi": ("rsi", 21,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 20,),
                "ema": ("ema", 3,),
                "hma": None,
                "vwma": ("vwma", 21,),
                "momentum": ("momentum", 21,),
                "stochastic": None,
                "macd": None,  # ("macd", 21,),
                "bollingerbands": ("bollingerbands", 36,),
                "triangle": None,
                "pivotpoint": ("pivotpoint", 0,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 1.5),
                "bbawe": ("bbawe", 20, 2.0, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 0.3,
                "rsi_high": 0.7,
            },
            "scores": {
                "rsi_factor": 1.0,
                "rsi_trend_factor": 0.5,
                "sma_ema_cross_factor": (-0.5, -0.5),  # no-div/div
                "ema_vwma_cross_factor": (-5, -5),
                "price_vwma_factor": 50.0,
                "ema_vwma_cross_bonus": 0,  # 1,2,3,5
                "rsi_ema_trend_div_factor": (-0.04, -0.04),
            }
        },
        "4hour": {
            "timeframe": "4h",
            "mode": "A",
            "depth": 56,
            "history": 56,
            "score-ratio": 6,
            "score-level": 0.05,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "volume_ema": ("ema", 8,),
                "rsi": ("rsi", 21,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma200": ("sma", 200,),
                "sma55": ("sma", 55,),
                "sma": ("sma", 20,),
                "ema": ("ema", 3,),
                "hma": None,
                "vwma": ("vwma", 21,),
                "momentum": ("momentum", 21,),
                "stochastic": None,
                "macd": None,  # ("macd", 21,),
                "bollingerbands": ("bollingerbands", 36,),
                "triangle": None,
                "pivotpoint": ("pivotpoint", 0,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 1.5),
                "bbawe": ("bbawe", 20, 2.0, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 0.3,
                "rsi_high": 0.7,
            },
            "scores": {
                "rsi_factor": 1.0,
                "rsi_trend_factor": 0.5,
                "sma_ema_cross_factor": (-0.5, -0.5),  # no-div/div
                "ema_vwma_cross_factor": (-5, -5),
                "price_vwma_factor": 50.0,
                "ema_vwma_cross_bonus": 0,  # 1,2,3,5
                "rsi_ema_trend_div_factor": (-0.04, -0.04),
            }   
        },
        "hourly": {
            "timeframe": "1h",
            "mode": "A", 
            "depth": 41,
            "history": 41,
            "score-ratio": 4,
            "score-level": 0.05,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "volume_ema": ("ema", 8,),
                "rsi": ("rsi", 21,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 20,),
                "ema": ("ema", 3,),
                "hma": None,
                "vwma": ("vwma", 21,),
                "momentum": ("momentum", 21,),
                "stochastic": None,
                "macd": None,  # ("macd", 21,),
                "bollingerbands": ("bollingerbands", 36,),
                "triangle": None,
                "pivotpoint": ("pivotpoint", 0,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 1.5),
                "bbawe": ("bbawe", 20, 2.0, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 0.3,
                "rsi_high": 0.7,
            },
            "scores": {
                "rsi_factor": 1.0,
                "rsi_trend_factor": 0.5,
                "sma_ema_cross_factor": (-0.5, -0.5),  # no-div/div
                "ema_vwma_cross_factor": (-5, -5),
                "price_vwma_factor": 50.0,
                "ema_vwma_cross_bonus": 0,  # 1,2,3,5
                "rsi_ema_trend_div_factor": (-0.04, -0.04),
            }
        },
        "15min": {
            "timeframe": "15m",
            "mode": "A",
            "depth": 41,
            "history": 41,
            "score-ratio": 2,
            "score-level": 0.05,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "volume_ema": ("ema", 8,),
                "rsi": ("rsi", 21,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 20,),
                "ema": ("ema", 3,),
                "hma": None,
                "vwma": ("vwma", 21,),
                "momentum": ("momentum", 21,),
                "stochastic": None,
                "macd": None,  # ("macd", 21,),
                "bollingerbands": ("bollingerbands", 36,),
                "triangle": None,
                "pivotpoint": ("pivotpoint", 0,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 1.5),
                "bbawe": ("bbawe", 20, 2.0, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 0.3,
                "rsi_high": 0.7,
            },
            "scores": {
                "rsi_factor": 1.0,
                "rsi_trend_factor": 0.5,
                "sma_ema_cross_factor": (-0.5, -0.5),  # no-div/div
                "ema_vwma_cross_factor": (-5, -5),
                "price_vwma_factor": 50.0,
                "ema_vwma_cross_bonus": 0,  # 1,2,3,5
                "rsi_ema_trend_div_factor": (-0.04, -0.04),
            }
        },
        "5min": {
            "timeframe": "5m",
            "mode": "A",
            "depth": 41,
            "history": 41,
            "score-ratio": 1,
            "score-level": 0.05,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "volume_ema": ("ema", 8,),
                "rsi": ("rsi", 21,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 20,),
                "ema": ("ema", 3,),
                "hma": None,
                "vwma": ("vwma", 21,),
                "momentum": ("momentum", 21,),
                "stochastic": None,
                "macd": None,  # ("macd", 21,),
                "bollingerbands": ("bollingerbands", 36,),
                "triangle": None,
                "pivotpoint": ("pivotpoint", 0,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 1.5),
                "bbawe": ("bbawe", 20, 2.0, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 0.3,
                "rsi_high": 0.7,
            },
            "scores": {
                "rsi_factor": 1.0,
                "rsi_trend_factor": 0.5,
                "sma_ema_cross_factor": (-0.5, -0.5),  # no-div/div
                "ema_vwma_cross_factor": (-5, -5),
                "price_vwma_factor": 50.0,
                "ema_vwma_cross_bonus": 0,  # 1,2,3,5
                "rsi_ema_trend_div_factor": (-0.04, -0.04),
            }
        },
        "1min": {
            "timeframe": "1m",
            "mode": "A",
            "depth": 41,
            "history": 41,
            "score-ratio": 0.5,
            "score-level": 0.05,
            "update-at-close": True,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 21,),  # or 14
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 20,),  # try another
                "ema": ("ema", 3,),   # try another
                "hma": ("hma", 8,),
                "vwma": ("vwma", 8,),
                "momentum": ("momentum", 20,),
                "stochastic": None,
                "macd": None,  # ("macd", 17,),
                "bollingerbands": None, # ("bollingerbands", 26,),
                "triangle": None,
                "pivotpoint": ("pivotpoint", 0,),  # classic or fibo
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 1.5),  # 0.75 is to low, 1.5 try, 3.0 can be to large or (40, 3.0)
                "bbawe": ("bbawe", 36, 2.0, 3.0, 5, 34, False),
            },
            "constants": {
                "rsi_low": 0.3,
                "rsi_high": 0.7,
            },
            "scores": {
                # "rsi_factor": 0.04,
                # "rsi_trend_factor": 0.2,
                # "ema_vwma_cross_factor": 0.5,
                # "price_vwma_factor": 5.0,
                # "hma_sma_cross_factor": -50,
                # "hma_vwma_cross_factor": 0,
                # "ema_vwma_cross_bonus": 0.05,
                # "rsi_hma_trend_div_factor": -1.0,
                "rsi_factor": 1.0,
                "rsi_trend_factor": 0.5,
                "sma_ema_cross_factor": (-0.5, -0.5),  # no-div/div
                "ema_vwma_cross_factor": (-5, -5),
                "price_vwma_factor": 50.0,
                "ema_vwma_cross_bonus": 0,  # 1,2,3,5
                "rsi_ema_trend_div_factor": (-0.04, -0.04),
            }
        },
        # "10sec": {
        #     "timeframe": "10s",
        #     "mode": "A",
        #     "depth": 100,
        #     "history": 100,
        #     "score-ratio": 0.5,
        #     "score-level": 0.05,
        #     "update-at-close": True,
        #     "signal-at-close": True,
        #     "indicators": {
        #         "price": ("price", 1,),
        #         "volume": ("volume", 0,),
        #         "rsi": ("rsi", 21,),  # or 14
        #         "stochrsi": ("stochrsi", 13, 13, 13),
        #         "sma": ("sma", 20,),  # try another
        #         "ema": ("ema", 3,),   # try another
        #         "hma": ("hma", 8,),
        #         "vwma": ("vwma", 8,),
        #         "momentum": ("momentum", 20,),
        #         "stochastic": None,
        #         "macd": None,  # ("macd", 17,),
        #         "bollingerbands": None, # ("bollingerbands", 26,),
        #         "triangle": None,
        #         "pivotpoint": ("pivotpoint", 0,),  # classic or fibo
        #         "tomdemark": ("tomdemark", 9),
        #         "atr": ("atr", 50, 5.0),  # 0.75 is to low, 1.5 try, 3.0 can be to large or (40, 3.0)  (50, 10.0)
        #         "bbawe": ("bbawe", 50, 2.0, 3.0, 5, 34, False),
        #     },
        #     "constants": {
        #         "rsi_low": 0.3,
        #         "rsi_high": 0.7,
        #     },
        #     "scores": {
        #         # "rsi_factor": 0.04,
        #         # "rsi_trend_factor": 0.2,
        #         # "ema_vwma_cross_factor": 0.5,
        #         # "price_vwma_factor": 5.0,
        #         # "hma_sma_cross_factor": -50,
        #         # "hma_vwma_cross_factor": 0,
        #         # "ema_vwma_cross_bonus": 0.05,
        #         # "rsi_hma_trend_div_factor": -1.0,
        #         "rsi_low": 0.3,
        #         "rsi_high": 0.7,
        #         "rsi_factor": 1.0,
        #         "rsi_trend_factor": 0.5,
        #         "sma_ema_cross_factor": (-0.5, -0.5),  # no-div/div
        #         "ema_vwma_cross_factor": (-5, -5),
        #         "price_vwma_factor": 50.0,
        #         "ema_vwma_cross_bonus": 0,  # 1,2,3,5
        #         "rsi_ema_trend_div_factor": (-0.04, -0.04),
        #     }
        # }
    }
}
