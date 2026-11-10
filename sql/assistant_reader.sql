-- The AI assistant's own database user. It can read the dbt marts and nothing else.
-- Run it once, as the user that runs dbt (on Neon, in the SQL Editor), with your own strong password.
-- Never save the real password in this file.

CREATE ROLE assistant_reader LOGIN PASSWORD 'choose-a-strong-password';

-- Read-only by default, and no query may run longer than 5 seconds
ALTER ROLE assistant_reader SET default_transaction_read_only = on;
ALTER ROLE assistant_reader SET statement_timeout = '5s';

-- It may read the marts: the tables there today, and the ones dbt rebuilds every weekday
GRANT USAGE ON SCHEMA analytics_marts TO assistant_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics_marts TO assistant_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics_marts GRANT SELECT ON TABLES TO assistant_reader;
