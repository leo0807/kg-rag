-- ClickHouse schema for CDC events from Debezium
-- Populated by backend/src/events/cdc_consumer.py

CREATE DATABASE IF NOT EXISTS aviation;

-- conversations CDC events
CREATE TABLE IF NOT EXISTS aviation.conversations_changes
(
    event_time        DateTime     DEFAULT now(),
    op                String,                      -- c=create u=update d=delete r=snapshot
    session_id        String,
    user_id           String,
    tenant_id         String,
    doc_id            String,
    query_count       Int32        DEFAULT 0,
    created_at        DateTime,
    updated_at        DateTime
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, session_id)
TTL event_time + INTERVAL 1 YEAR;

-- query_feedback CDC events
CREATE TABLE IF NOT EXISTS aviation.query_feedback_changes
(
    event_time        DateTime     DEFAULT now(),
    op                String,
    feedback_id       String,
    session_id        String,
    user_id           String,
    score             Int8         DEFAULT 0,
    comment           String       DEFAULT '',
    created_at        DateTime
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, feedback_id)
TTL event_time + INTERVAL 1 YEAR;

-- llm_usage CDC events
CREATE TABLE IF NOT EXISTS aviation.llm_usage_changes
(
    event_time        DateTime     DEFAULT now(),
    op                String,
    usage_id          String,
    user_id           String,
    tenant_id         String,
    model             String,
    prompt_tokens     Int32        DEFAULT 0,
    completion_tokens Int32        DEFAULT 0,
    cost_usd          Float64      DEFAULT 0,
    created_at        DateTime
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, usage_id)
TTL event_time + INTERVAL 1 YEAR;

-- Backing table for the hourly usage summary (target of materialized view)
CREATE TABLE IF NOT EXISTS aviation.usage_summary
(
    hour              DateTime,
    tenant_id         String,
    model             String,
    total_queries     Int64,
    total_tokens      Int64,
    total_cost        Float64
)
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, tenant_id, model);

-- Materialized view: aggregate llm_usage_changes into hourly buckets
CREATE MATERIALIZED VIEW IF NOT EXISTS aviation.mv_usage_summary
TO aviation.usage_summary
AS
SELECT
    toStartOfHour(event_time)                       AS hour,
    tenant_id,
    model,
    count()                                          AS total_queries,
    sum(prompt_tokens + completion_tokens)           AS total_tokens,
    sum(cost_usd)                                    AS total_cost
FROM aviation.llm_usage_changes
WHERE op IN ('c', 'u')
GROUP BY hour, tenant_id, model;
