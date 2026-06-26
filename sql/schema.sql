PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    pmcid TEXT,
    doi TEXT,
    license TEXT NOT NULL,
    commercial_use_allowed INTEGER NOT NULL CHECK (commercial_use_allowed IN (0, 1)),
    title TEXT NOT NULL,
    authors_json TEXT NOT NULL,
    journal TEXT NOT NULL,
    year INTEGER NOT NULL,
    url TEXT NOT NULL,
    date_accessed TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS figures (
    figure_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    figure_label TEXT NOT NULL,
    caption TEXT NOT NULL,
    image_path TEXT,
    panel_label TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    figure_id TEXT NOT NULL REFERENCES figures(figure_id),
    task_type TEXT NOT NULL,
    question TEXT NOT NULL,
    answer_choices_json TEXT NOT NULL,
    gold_answer TEXT NOT NULL,
    rationale TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    ambiguity TEXT NOT NULL,
    failure_type TEXT NOT NULL,
    safety_level TEXT NOT NULL,
    review_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    expert_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    corrected_answer TEXT,
    reviewer_notes TEXT,
    confidence INTEGER CHECK (confidence BETWEEN 1 AND 5),
    time_spent_seconds INTEGER,
    reviewed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_runs (
    run_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    model_name TEXT NOT NULL,
    model_answer TEXT NOT NULL,
    correct INTEGER NOT NULL CHECK (correct IN (0, 1)),
    error_type TEXT,
    raw_output TEXT,
    evaluated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_failure_type ON tasks(failure_type);
CREATE INDEX IF NOT EXISTS idx_tasks_review_status ON tasks(review_status);
CREATE INDEX IF NOT EXISTS idx_model_runs_model_name ON model_runs(model_name);
