import sys
import json

import matplotlib.pyplot as plt

import numpy as np

from datetime import datetime

from talib import SMA as ta_SMA
from talib import BBANDS as ta_BBANDS

y1 = []
y2 = []
x = []

doy1 = True
doy2 = False
dopng = False
doshow = True
sma = False
bbs = False
period = 20
fname = "balance.json"

if len(sys.argv) > 2:
    fname = sys.argv[2]

if len(sys.argv) > 1:   
    for argv in sys.argv:
        if argv == "sma":
            sma = True
        elif argv == "bbs":
            bbs = True
        elif argv == "total":
            doy1 = True
            doy2 = False
        elif argv == "asset":
            doy1 = False
            doy2 = True
        elif argv == "both":
            doy1 = True
            doy2 = True
        elif argv == "png":
            dopng = True
        elif argv == "show":
            doshow = True
        elif argv == "hide":
            doshow = False
        else:
            try:
                v = int(argv)
                if 0 < v < 365:
                    period = v
            except ValueError:
                pass


with open(fname, "r") as f:
    data = json.loads(f.read())
    
if data:
    for v in data:
        x.append(datetime.strptime(v['date'], '%Y-%m-%dT%H:%M:%SZ').strftime('%y-%m-%d'))
        y1.append(v['asset-balance'])
        y2.append(v['balance'])

plt.xticks(rotation=45, ha="right")

if doy1:
    plt.plot(x, y1, label='cap')

if doy2:
    plt.plot(x, y2, label='asset')

if sma and len(y1) > 1:
    if doy1:
        length = min(len(y1)-1, period)
        smas1 = ta_SMA(np.array(y1), length)

        diff = len(y1) - len(smas1)
        if diff:
            smas1 = [smas1[0]]*diff + smas1

        plt.plot(x, smas1, label='MA20_cap')

    if doy2:
        length = min(len(y2)-1, period)
        smas2 = ta_SMA(np.array(y2), length)

        diff = len(y2) - len(smas2)
        if diff:
            smas2 = [smas2[0]]*diff + smas2

        plt.plot(x, smas2, label='MA20_asset')

if bbs and len(y1) > 1:
    if doy1:
        length = min(len(y1)-1, period)
        bb_tops1, bb_mas1, bb_bottoms1 = ta_BBANDS(np.array(y1), timeperiod=length, nbdevup=2, nbdevdn=2, matype=0)

        diff = len(y1) - len(bb_mas1)
        if diff:
            bb_tops1 = [bb_tops1[0]]*diff + bb_tops1
            bb_bottoms1 = [bb_bottoms1[0]]*diff + bb_bottoms1
        
        plt.plot(x, bb_tops1, label='BB_t_cap')
        plt.plot(x, bb_bottoms1, label='BB_b_cap')
        
        plt.fill_between(x, bb_tops1, bb_bottoms1, color="blue", alpha=0.2)

    if doy2:
        length = min(len(y2)-1, period)
        bb_tops2, bb_mas2, bb_bottoms2 = ta_BBANDS(np.array(y2), timeperiod=length, nbdevup=2, nbdevdn=2, matype=0)

        diff = len(y2) - len(bb_mas2)
        if diff:
            bb_tops2 = [bb_tops2[0]]*diff + bb_tops2
            bb_bottoms2 = [bb_bottoms2[0]]*diff + bb_bottoms2
        
        plt.plot(x, bb_tops2, label='BB_t_asset')
        plt.plot(x, bb_bottoms2, label='BB_b_asset')
        
        plt.fill_between(x, bb_tops2, bb_bottoms2, color="blue", alpha=0.2)

title = fname[:-5].split('/')
if len(title) > 1:
    title = title[-2]

plt.title(title)
plt.legend()
plt.subplots_adjust(bottom=0.17, left=0.17)

if dopng:
    plt.savefig(fname.replace(".json", ".png"), transparent=True)
    
if doshow:
    plt.show()

