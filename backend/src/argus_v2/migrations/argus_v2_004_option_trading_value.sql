ALTER TABLE argus_v2_option_chain_levels
    ADD COLUMN call_trading_value REAL;

ALTER TABLE argus_v2_option_chain_levels
    ADD COLUMN put_trading_value REAL;
