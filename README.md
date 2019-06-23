SIIS Strategy/Scalper Indicator Information System
==================================================

**The redaction of this document is in progress.**

Abstract
--------

SiiS is a autotrading bot for forex, indices and crypto currencies markets.
It also support semi-automated trading in way to manage your entry and exits
with more possibilities than an exchanges allow.

This version is more a functionnal prototype than a final professional trading tool.
It is developped in Python3, using TA-lib, numpy and matplotlib for the basic charting client.

A more performant, but still in developpement, SiiS revisited is available at [github:siis-rev](https://github.com/dream-overflow/siis-rev)


Features
--------

* Initially developped for Linux, but should work on Window or MacOSX
* Traditionnals and crypto markets brokers (traders) are supported
    * Binance
    * Bitmex
    * IG
    * 1broker (obsolete)
* Some others data-source in way to gets prices/volumes data
   * HistData (only to import manually downloaded files)
   * AlphaVantage (WIP)
   * Tiingo (WIP)
* Fetching OHLC and ticks history data in PostgreSQL or MySQL DB
* Multiple instance can run at the same time
* Many strategies and markets can run on a same instance (test with 100+ markets on a single instance)
* Connection with API key (open-source you can check than yours API keys are safe with SiiS)
* Configuration of multiple accounts identities
* Configuration of multiple profiles and appliances (an appliance is a context of a strategy)
    * Combine one or more appliance to a profiles
    * Configure multiple appliances and profiles with different options
* Backtesting
* Paper-mode (simulate a broker for spot and margin)
* Live-mode trading on your broker account
* Interactive command lien interface
    * Backtesting with a slow down or real time factor allowing you to replay an history
      and doing manual and semi-automated trading
* Try as possible to take-care of the spread of the market and the commissions
* Compute the average unit price of owned assets on Binance
* Display account detail and assets quantities
* Display tickers and markets informations
* Display per strategy current (active or pending) trades, trades history and performance
* Manage multiple timeframe
* Common indicators are supported (RSI, SMA, BBANDS, ATR...)
* Pure signal strategies are possibles in way to only generating some signal
* Desktop notification on Linux via dbus
* Audible notification on Linux via aplay
* Basic Discord WebHook notifier (have to be redone)
* 3 initials strategies (1 for bitcoin/etherum, 1 for forex, 1 for majors altcoins)
* WebHook of TradingView strategies with an example of a such strategy (need an extra JS plugin on the browser)
* SocialCopy capacities (deprecated for now, was done initially on 1broker, some works have to be redone)
* Manual per trade directive (more directive will be coming)
* Manual regions of interest per market strategy to help the bot filtering some signals (WIP)
    * Range region
    * Trend channel region

### Donation ###

BTC: 1GVdwcVrvvbqBgzNMii6tGNhTYnGvsJZFE
ETH: 0xd9cbda09703cdd4df9aeabf63f23be8da19ca9bf


Installation
------------

Need Python3.6 or Python3.7 on your system.
Tested on Debian, Ubuntu and Fedora.

### Create a PIP virtual env ###

```
python -m venv siis.venv
source siis.venv/bin/activate
```

You need to active it each time you open your terminal before running SiiS.

From deps/ directory, first install TA-Lib :

```
tar xvzf deps/ta-lib-0.4.0-src.tar.gz
cd ta-lib
./configure
make
```

```
sudo make install
```

copy the content of the include folder into siis.venv/include/ta-lib/
and copy the .a and .so to siis.venv/lib/pythonX.Y/site-packages


### Python dependencies ###

pip install -r requirements.txt


Before running the lib folder containing TA-Lib must be in the LD_LIBRARY_PATH :

With, if installed in the default directory :

export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH


### Database ###

Prefers the PostgreSQL database server. For now SiiS does not bulk data insert, the performance
with PostgreSQL are OK, but lesser on MySQL.

The sql/ directory contains the SQL script for the two databases and the first line of comment
in these files describe a possible way to install them.


Configuration
-------------

First running will create a .siis folder on Linux based systems, and into UserData/siis on Windows.

### <.siis/config/>config.py ###

You have an initial file in config/config.py. Do not modifiy the original.

...


### <.siis/config/>appliances.py ###

You have an initial file in config/appliances.py. Do not modify the original.

...


### <.siis/config/>identities.py ###

This is the more sensible file, which contains your API keys.
You have a config/identities.py.template file. Do not modify this file it will not be read.


Running
-------

python siis.py <identity> [--help, --options...]


Importing some data
-------------------

...


Backtesting
-----------

...


Paper-mode
----------

...


Live-mode
---------

...


Data storage
------------

...


Troubles
--------

TA-lib is not found : look you have installed it, and may be you have to export your LD_LIBRARY_PATH.

