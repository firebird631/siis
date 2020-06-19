About
=====

Its a simple Qt view containing matplotlib charts.
Works only as a receiver of the stream coming from the monitor,
through a Unix FIFO. 

This is only for developpement usage, its not efficient,
not fully featured.

Consider this client as deprecated.

@deprecated now uses the webtrader chart client

Usage
=====

python client.py </tmp/pathtofifofile> --appliance=<appliance-id> --market=<market-id>

To show a specific market performance and charting.
