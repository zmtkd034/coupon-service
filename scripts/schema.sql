CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    total_qty     INTEGER NOT NULL,
    remaining_qty INTEGER NOT NULL CHECK (remaining_qty >= 0)
);

CREATE TABLE IF NOT EXISTS coupon_issues (
    id        BIGSERIAL PRIMARY KEY,
    event_id  INTEGER     NOT NULL REFERENCES events(id),
    user_id   TEXT        NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, user_id)
);
