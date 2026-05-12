ALTER TABLE argus_v2_market_reaction_snapshots
    ADD COLUMN spot_foreign_net_buy REAL;

ALTER TABLE argus_v2_market_reaction_snapshots
    ADD COLUMN spot_institution_net_buy REAL;

ALTER TABLE argus_v2_market_reaction_snapshots
    ADD COLUMN spot_individual_net_buy REAL;
