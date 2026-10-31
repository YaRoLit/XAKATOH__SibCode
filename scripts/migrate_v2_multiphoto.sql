-- Стабильная версия 2: группа фото на (batch, object).
-- Идемпотентно. FK на photo-таблицы из analysis_reports не ставим.

BEGIN;

ALTER TABLE processing_queue ADD COLUMN IF NOT EXISTS survey_ids jsonb;
ALTER TABLE processing_queue ADD COLUMN IF NOT EXISTS primary_survey_id integer;
ALTER TABLE processing_queue ADD COLUMN IF NOT EXISTS batch_id varchar(64);
ALTER TABLE processing_queue ADD COLUMN IF NOT EXISTS capture_date date;

UPDATE processing_queue q
SET
    survey_ids = COALESCE(q.survey_ids, jsonb_build_array(q.survey_id)),
    primary_survey_id = COALESCE(q.primary_survey_id, q.survey_id),
    batch_id = COALESCE(q.batch_id, s.batch_id),
    capture_date = COALESCE(
        q.capture_date,
        CASE
            WHEN COALESCE(s.metadata->>'datetime_original', '') <> ''
            THEN replace(split_part(s.metadata->>'datetime_original', ' ', 1), ':', '-')::date
            ELSE NULL
        END,
        s.created_at::date
    )
FROM surveys s
WHERE s.id = q.survey_id
  AND (q.survey_ids IS NULL OR q.primary_survey_id IS NULL OR q.batch_id IS NULL OR q.capture_date IS NULL);

CREATE INDEX IF NOT EXISTS ix_queue_batch_id ON processing_queue (batch_id);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'processing_queue_survey_id_key'
    ) THEN
        ALTER TABLE processing_queue DROP CONSTRAINT processing_queue_survey_id_key;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'processing_queue_survey_id_fkey'
    ) THEN
        ALTER TABLE processing_queue DROP CONSTRAINT processing_queue_survey_id_fkey;
    END IF;
END $$;

ALTER TABLE processing_queue ALTER COLUMN survey_id DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_queue_batch_object'
    ) THEN
        ALTER TABLE processing_queue
            ADD CONSTRAINT uq_queue_batch_object UNIQUE (batch_id, object_id);
    END IF;
END $$;

ALTER TABLE analysis_reports ADD COLUMN IF NOT EXISTS primary_survey_id integer;
ALTER TABLE analysis_reports ADD COLUMN IF NOT EXISTS survey_ids jsonb;
ALTER TABLE analysis_reports ADD COLUMN IF NOT EXISTS batch_id varchar(64);
ALTER TABLE analysis_reports ADD COLUMN IF NOT EXISTS capture_date date;

UPDATE analysis_reports r
SET
    primary_survey_id = COALESCE(r.primary_survey_id, r.survey_id),
    survey_ids = COALESCE(r.survey_ids, jsonb_build_array(r.survey_id)),
    batch_id = COALESCE(r.batch_id, s.batch_id),
    capture_date = COALESCE(r.capture_date, r.captured_at::date, s.created_at::date)
FROM surveys s
WHERE s.id = r.survey_id
  AND (r.primary_survey_id IS NULL OR r.survey_ids IS NULL OR r.batch_id IS NULL OR r.capture_date IS NULL);

UPDATE analysis_reports
SET
    primary_survey_id = COALESCE(primary_survey_id, survey_id),
    survey_ids = COALESCE(survey_ids, jsonb_build_array(survey_id)),
    capture_date = COALESCE(capture_date, captured_at::date)
WHERE primary_survey_id IS NULL OR survey_ids IS NULL OR capture_date IS NULL;

CREATE INDEX IF NOT EXISTS ix_analysis_reports_batch_id ON analysis_reports (batch_id);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'analysis_reports_survey_id_key'
    ) THEN
        ALTER TABLE analysis_reports DROP CONSTRAINT analysis_reports_survey_id_key;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'ix_analysis_reports_survey_id'
    ) THEN
        DROP INDEX ix_analysis_reports_survey_id;
    END IF;
END $$;

ALTER TABLE analysis_reports ALTER COLUMN survey_id DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_analysis_reports_batch_object'
    ) THEN
        ALTER TABLE analysis_reports
            ADD CONSTRAINT uq_analysis_reports_batch_object UNIQUE (batch_id, object_id);
    END IF;
END $$;

COMMIT;
