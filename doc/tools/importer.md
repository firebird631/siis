# Importer tool #

This tool allow you to import bulk of data from differents format to the database.


## Supported formats ##

* SIIS version 1.0.0
* MT4 csv from 1m to weekly


### SIIS 1.0.0 ###

The SIIS format is more easy to import, because no options are required, the manifest is included into the first row of the file.
Multiples timeframes can be combined into a single file.

Example :

```
python siis.py real --import --filename=ig.com-CS.D.EURUSD.MINI.IP-any.siis
```

will import the content of the file, depending of the header of the file.


### MT4 csv ###

The MT4 csv format is common, but you have only one timeframe per file.
In addition the broker identifier, market identifier and timeframe must be specified. 

Example :

```
python siis.py real --import --filename=EURUSD60.csv --broker=ig.com --market=CS.D.EURUSD.MINI.IP --timeframe=1m
```

will import a MT4 csv file of 1m OHLCs to the database, into the ig.com / CS.D.EURUSD.MINI.IP market.


## Others options ##

Two mandatories options permit to limit the range of data to import :

* --from= only from the specified datetime 
* --to= until the specified datetime
