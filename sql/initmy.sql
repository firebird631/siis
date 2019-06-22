-- initial, create tables for mysql
-- usage example :
-- $ mysql -u root -p
-- > CREATE DATABASE siis;
-- > CREATE USER 'siis'@'localhost' IDENTIFIED BY 'siis';
-- > GRANT ALL PRIVILEGES ON siis TO 'siis'@'localhost';
-- > FLUSH PRIVILEGES;
-- $ mysql -u siis -D siis -p < initmy.sql

-- market
CREATE TABLE IF NOT EXISTS market(
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    broker_id VARCHAR(255) NOT NULL, market_id VARCHAR(255) NOT NULL, symbol VARCHAR(32) NOT NULL,
    base VARCHAR(32) NOT NULL, base_display VARCHAR(32) NOT NULL, base_precision VARCHAR(32) NOT NULL,
    quote VARCHAR(32) NOT NULL, quote_display VARCHAR(32) NOT NULL, quote_precision VARCHAR(32) NOT NULL,
    expiry VARCHAR(32) NOT NULL, timestamp BIGINT NOT NULL,
    lot_size VARCHAR(32) NOT NULL, contract_size VARCHAR(32) NOT NULL, base_exchange_rate VARCHAR(32) NOT NULL,
    min_size VARCHAR(32) NOT NULL, max_size VARCHAR(32) NOT NULL, step_size VARCHAR(32) NOT NULL,
    min_notional VARCHAR(32) NOT NULL,
    value_per_pip VARCHAR(32) NOT NULL, one_pip_means VARCHAR(32) NOT NULL,
    margin_factor VARCHAR(32),
    market_type INTEGER NOT NULL, unit_type INTEGER NOT NULL,
    bid VARCHAR(32) NOT NULL, ofr VARCHAR(32) NOT NULL,
    maker_fee VARCHAR(32) NOT NULL DEFAULT '0', taker_fee VARCHAR(32) NOT NULL DEFAULT '0', commission VARCHAR(32) NOT NULL DEFAULT '0',
    UNIQUE KEY(broker_id, market_id));

-- asset
CREATE TABLE IF NOT EXISTS asset(
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    broker_id VARCHAR(255) NOT NULL, asset_id VARCHAR(255) NOT NULL,
    last_trade_id VARCHAR(32) NOT NULL, timestamp BIGINT NOT NULL,
    quantity VARCHAR(32) NOT NULL, price VARCHAR(32) NOT NULL, quote_symbol VARCHAR(32) NOT NULL,
    UNIQUE(broker_id, asset_id));

-- user_trade
CREATE TABLE IF NOT EXISTS user_trade(
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    broker_id VARCHAR(255) NOT NULL, market_id VARCHAR(255) NOT NULL,
    appliance_id VARCHAR(255) NOT NULL, trade_id INTEGER NOT NULL, trade_type INTEGER NOT NULL,
    timestamp BIGINT NOT NULL, direction INTEGER NOT NULL,
    price VARCHAR(32) NOT NULL, stop_loss VARCHAR(32) NOT NULL, take_profit VARCHAR(32) NOT NULL,
    quantity VARCHAR(32) NOT NULL, entry_quantity VARCHAR(32) NOT NULL, exit_quantity VARCHAR(32) NOT NULL,
    profit_loss VARCHAR(32) NOT NULL, timeframes VARCHAR(256) NOT NULL,
    entry_status INTEGER NOT NULL, exit_status INTEGER NOT NULL,
    entry_order_id VARCHAR(32), exit1_order_id VARCHAR(32), exit2_order_id VARCHAR(32), exit3_order_id VARCHAR(32),
    entry_ref_order_id VARCHAR(32), exit1_ref_order_id VARCHAR(32), exit2_ref_order_id VARCHAR(32), exit3_ref_order_id VARCHAR(32),
    position_id VARCHAR(32),
    copied_position_id VARCHAR(32),
    conditions VARCHAR(1024),
    UNIQUE KEY(broker_id, market_id, appliance_id, trade_id));

-- candle
CREATE TABLE IF NOT EXISTS candle(
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    broker_id VARCHAR(255) NOT NULL, market_id VARCHAR(255) NOT NULL,
    timestamp BIGINT NOT NULL, timeframe INTEGER NOT NULL,
    bid_open VARCHAR(32) NOT NULL, bid_high VARCHAR(32) NOT NULL, bid_low VARCHAR(32) NOT NULL, bid_close VARCHAR(32) NOT NULL,
    ask_open VARCHAR(32) NOT NULL, ask_high VARCHAR(32) NOT NULL, ask_low VARCHAR(32) NOT NULL, ask_close VARCHAR(32) NOT NULL,
    volume VARCHAR(48) NOT NULL,
    UNIQUE KEY(broker_id, market_id, timestamp, timeframe));
