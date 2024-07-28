ALTER TABLE market 
ADD settlement VARCHAR(32) NOT NULL DEFAULT(''),
ADD settlement_display VARCHAR(32) NOT NULL DEFAULT(''),
ADD settlement_precision VARCHAR(32) NOT NULL DEFAULT('8');

