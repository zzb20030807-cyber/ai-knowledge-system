-- =========================================================
-- AI Knowledge System
-- Database Initialization
-- =========================================================

-- 1. pgvector
CREATE EXTENSION IF NOT EXISTS vector;


-- =========================================================
-- 2. users
-- =========================================================

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- =========================================================
-- 3. chat_sessions
-- =========================================================

CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    title VARCHAR(100) DEFAULT '新聊天',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,

    CONSTRAINT fk_chat_sessions_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);


-- =========================================================
-- 4. chat_messages
-- =========================================================

CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    user_message TEXT NOT NULL,
    ai_message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id INTEGER,

    CONSTRAINT fk_chat_session
        FOREIGN KEY (session_id)
        REFERENCES chat_sessions(id)
        ON DELETE CASCADE
);


-- =========================================================
-- 5. documents
-- =========================================================

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector,
    filename VARCHAR,
    page_number INTEGER,
    chunk_id INTEGER,
    user_id INTEGER NOT NULL,

    CONSTRAINT fk_documents_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);


-- =========================================================
-- 6. Indexes
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id
ON chat_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id
ON chat_messages(session_id);

CREATE INDEX IF NOT EXISTS idx_documents_user_id
ON documents(user_id);

CREATE INDEX IF NOT EXISTS idx_documents_user_filename
ON documents(user_id, filename);