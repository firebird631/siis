-- initial, create tables for postgresql
-- usage example :
-- $ psql -h localhost -U root -W -p 5432
-- > CREATE DATABASE siis;
-- > CREATE USER siis WITH ENCRYPTED PASSWORD 'siis';
-- > GRANT ALL PRIVILEGES ON DATABASE siis TO siis;
-- $ psql -h localhost -d siis -U siis -W -p 5432 -a -q -f initpg.sql

-- market
CREATE TABLE IF NOT EXISTS market(
    id SERIAL PRIMARY KEY,
    broker_id VARCHAR(255) NOT NULL, market_id VARCHAR(255) NOT NULL, symbol VARCHAR(32) NOT NULL,
    market_type INTEGER NOT NULL DEFAULT 0, unit_type INTEGER NOT NULL DEFAULT 0, contract_type INTEGER NOT NULL DEFAULT 0,
    trade_type INTEGER NOT NULL DEFAULT 0, orders INTEGER NOT NULL DEFAULT 0,
    base VARCHAR(32) NOT NULL, base_display VARCHAR(32) NOT NULL, base_precision VARCHAR(32) NOT NULL,
    quote VARCHAR(32) NOT NULL, quote_display VARCHAR(32) NOT NULL, quote_precision VARCHAR(32) NOT NULL,
    expiry VARCHAR(32) NOT NULL, timestamp BIGINT NOT NULL,
    lot_size VARCHAR(32) NOT NULL, contract_size VARCHAR(32) NOT NULL, base_exchange_rate VARCHAR(32) NOT NULL,
    value_per_pip VARCHAR(32) NOT NULL, one_pip_means VARCHAR(32) NOT NULL, margin_factor VARCHAR(32) NOT NULL DEFAULT '1.0',
    min_size VARCHAR(32) NOT NULL, max_size VARCHAR(32) NOT NULL, step_size VARCHAR(32) NOT NULL,
    min_notional VARCHAR(32) NOT NULL, max_notional VARCHAR(32) NOT NULL, step_notional VARCHAR(32) NOT NULL,
    min_price VARCHAR(32) NOT NULL, max_price VARCHAR(32) NOT NULL, step_price VARCHAR(32) NOT NULL,
    maker_fee VARCHAR(32) NOT NULL DEFAULT '0', taker_fee VARCHAR(32) NOT NULL DEFAULT '0',
    maker_commission VARCHAR(32) NOT NULL DEFAULT '0', taker_commission VARCHAR(32) NOT NULL DEFAULT '0',
    UNIQUE(broker_id, market_id));

-- asset
CREATE TABLE IF NOT EXISTS asset(
    id SERIAL PRIMARY KEY,
    broker_id VARCHAR(255) NOT NULL, account_id VARCHAR(255) NOT NULL, asset_id VARCHAR(255) NOT NULL,
    last_trade_id VARCHAR(32) NOT NULL, timestamp BIGINT NOT NULL,
    quantity VARCHAR(32) NOT NULL, price VARCHAR(32) NOT NULL, quote_symbol VARCHAR(32) NOT NULL,
    UNIQUE(broker_id, account_id, asset_id));

-- ohlc
CREATE TABLE IF NOT EXISTS ohlc(
    id SERIAL PRIMARY KEY,
    broker_id VARCHAR(255) NOT NULL, market_id VARCHAR(255) NOT NULL,
    timestamp BIGINT NOT NULL, timeframe INTEGER NOT NULL,
    bid_open VARCHAR(32) NOT NULL, bid_high VARCHAR(32) NOT NULL, bid_low VARCHAR(32) NOT NULL, bid_close VARCHAR(32) NOT NULL,
    ask_open VARCHAR(32) NOT NULL, ask_high VARCHAR(32) NOT NULL, ask_low VARCHAR(32) NOT NULL, ask_close VARCHAR(32) NOT NULL,
    volume VARCHAR(48) NOT NULL,
    UNIQUE(broker_id, market_id, timestamp, timeframe));

-- user_trade
CREATE TABLE IF NOT EXISTS user_trade(
    id SERIAL PRIMARY KEY,
    broker_id VARCHAR(255) NOT NULL, market_id VARCHAR(255) NOT NULL, account_id VARCHAR(255) NOT NULL,
    appliance_id VARCHAR(255) NOT NULL,
    trade_id INTEGER NOT NULL,
    trade_type INTEGER NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    operations TEXT NOT NULL DEFAULT '{}',
    UNIQUE(broker_id, account_id, market_id, appliance_id, trade_id))

-- user_trader
CREATE TABLE IF NOT EXISTS user_trader(
    id SERIAL PRIMARY KEY,
    broker_id VARCHAR(255) NOT NULL, account_id VARCHAR(255) NOT NULL, market_id VARCHAR(255) NOT NULL,
    appliance_id VARCHAR(255) NOT NULL,
    activity INTEGER NOT NULL DEFAULT 1,
    data TEXT NOT NULL DEFAULT '{}',
    regions TEXT NOT NULL DEFAULT '{}',
    UNIQUE(broker_id, account_id, market_id, appliance_id))
