CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE articles (
    id                   SERIAL PRIMARY KEY,
    url                  TEXT UNIQUE,
    title                TEXT,
    content              TEXT,
    product_category     TEXT,
    product_sub_category TEXT,
    related_urls         JSONB,
    scraped_at           TIMESTAMP
);

CREATE TABLE article_chunks (
    id              SERIAL PRIMARY KEY,
    article_id      INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    chunk_index     INTEGER,
    chunk_text      TEXT,
    embedding       vector(1536),
    UNIQUE(article_id, chunk_index)
);

CREATE TABLE questions (
    id              SERIAL PRIMARY KEY,
    article_id      INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    question_text   TEXT,
    generated_at    TIMESTAMP DEFAULT now()
);

CREATE TABLE users (
    id                       SERIAL PRIMARY KEY,
    tenant_name              TEXT,
    org_id                   TEXT UNIQUE,
    product                  TEXT,
    success_plan             TEXT,
    timezone                 TEXT,
    phone_number             TEXT,
    can_create_case          BOOLEAN DEFAULT true,
    is_chat_transfer_allowed BOOLEAN DEFAULT true,
    is_authenticated         BOOLEAN DEFAULT false
);

CREATE TABLE cases (
    id              SERIAL PRIMARY KEY,
    case_number     TEXT UNIQUE,
    user_id         INTEGER REFERENCES users(id),
    tenant_name     TEXT,
    org_id          TEXT,
    subject         TEXT,
    description     TEXT,
    severity        INTEGER CHECK (severity BETWEEN 1 AND 4),
    status          TEXT DEFAULT 'open',
    created_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE sessions (
    id              TEXT PRIMARY KEY,
    state_json      JSONB,
    updated_at      TIMESTAMP DEFAULT now()
);

CREATE INDEX ON article_chunks USING hnsw (embedding vector_cosine_ops);

-- Chainlit data layer tables (required for thread persistence and feedback)
-- Schema matches chainlit v2.10.0 chainlit_data_layer.py expectations
CREATE TABLE IF NOT EXISTS "Thread" (
    id TEXT PRIMARY KEY,
    name TEXT,
    metadata JSONB,
    tags TEXT[],
    "userId" TEXT,
    "userIdentifier" TEXT,
    "createdAt" TIMESTAMP DEFAULT now(),
    "updatedAt" TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "Step" (
    id TEXT PRIMARY KEY,
    "threadId" TEXT REFERENCES "Thread"(id) ON DELETE CASCADE,
    "parentId" TEXT,
    name TEXT,
    type TEXT,
    input TEXT,
    output TEXT,
    metadata JSONB DEFAULT '{}',
    "showInput" TEXT DEFAULT 'json',
    "isError" BOOLEAN DEFAULT false,
    "createdAt" TIMESTAMP DEFAULT now(),
    "startTime" TIMESTAMP,
    "endTime" TIMESTAMP
);

CREATE TABLE IF NOT EXISTS "Element" (
    id TEXT PRIMARY KEY,
    "threadId" TEXT REFERENCES "Thread"(id) ON DELETE CASCADE,
    "stepId" TEXT,
    metadata JSONB,
    mime TEXT,
    name TEXT,
    "objectKey" TEXT,
    url TEXT,
    "chainlitKey" TEXT,
    display TEXT,
    size TEXT,
    language TEXT,
    page INTEGER,
    props JSONB,
    "createdAt" TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "Feedback" (
    id TEXT PRIMARY KEY,
    "stepId" TEXT,
    name TEXT,
    value FLOAT,
    comment TEXT,
    "createdAt" TIMESTAMP DEFAULT now()
);
