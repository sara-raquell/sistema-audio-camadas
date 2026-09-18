
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS audios (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    original_name   VARCHAR NOT NULL,
    original_ext    VARCHAR NOT NULL,
    mime_type       VARCHAR,
    size_bytes      INTEGER NOT NULL,
    duration_sec    FLOAT,
    sample_rate     INTEGER,
    channels        INTEGER,
    bitrate         INTEGER,
    processing_type VARCHAR NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    path_original   VARCHAR NOT NULL,
    path_processed  VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_audios_created_at ON audios (created_at DESC);
