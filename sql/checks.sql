-- Data quality checks: each query counts bad rows. 0 = pass.

-- check: trades_without_valuations
SELECT COUNT(*) FROM dim_trade t
WHERE NOT EXISTS (SELECT 1 FROM fact_valuations v WHERE v.trade_id = t.trade_id);

-- check: valuations_before_trade_date
SELECT COUNT(*) FROM fact_valuations v
JOIN dim_trade t USING (trade_id)
WHERE v.date < t.trade_date;

-- check: dates_with_missing_market_data
SELECT COUNT(*) FROM (
    SELECT d.date FROM dim_date d
    LEFT JOIN fact_market_prices m USING (date)
    GROUP BY d.date
    HAVING COUNT(m.series) <> 12
) AS incomplete_dates;

-- check: non_positive_prices
SELECT COUNT(*) FROM fact_market_prices
WHERE asset_class IN ('EQUITY', 'FX') AND value <= 0;

-- check: bond_fields_on_non_bonds
SELECT COUNT(*) FROM dim_trade
WHERE instrument_type <> 'BOND' AND (coupon_rate IS NOT NULL OR maturity_years IS NOT NULL);

-- check: dv01_outside_bonds
SELECT COUNT(*) FROM fact_valuations v
JOIN dim_trade t USING (trade_id)
WHERE t.instrument_type <> 'BOND' AND v.dv01 <> 0;

-- check: matured_pnl_changes_after_maturity
SELECT COUNT(*) FROM (
    SELECT trade_id FROM fact_valuations
    WHERE status = 'MATURED'
    GROUP BY trade_id
    HAVING COUNT(DISTINCT pnl) > 1
) AS moving_matured_trades;
