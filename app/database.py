import os

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector


load_dotenv()


# =========================
# 连接 PostgreSQL 数据库
# =========================

connection = psycopg.connect(
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "5432")),
    dbname=os.getenv("DB_NAME", "ai_knowledge"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD"),
    autocommit=True
)

register_vector(connection)

print("数据库连接成功！")


# =========================
# 保存聊天记录
# =========================

def save_message(user_message, ai_message, session_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat_messages
            (user_message, ai_message, session_id)
            VALUES (%s, %s, %s)
            """,
            (
                user_message,
                ai_message,
                session_id
            )
        )

    connection.commit()


# =========================
# 创建新的聊天
# =========================

def create_session(user_id, title="新聊天"):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat_sessions
            (title, user_id)
            VALUES (%s, %s)
            RETURNING id
            """,
            (
                title,
                user_id
            )
        )

        session_id = cursor.fetchone()[0]

    connection.commit()

    return session_id


# =========================
# 获取当前用户的所有聊天
# =========================

def get_sessions(user_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                title
            FROM chat_sessions
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,)
        )

        sessions = cursor.fetchall()

    return sessions


# =========================
# 检查聊天是否属于当前用户
# =========================

def check_session_owner(session_id, user_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM chat_sessions
            WHERE id = %s
              AND user_id = %s
            """,
            (
                session_id,
                user_id
            )
        )

        return cursor.fetchone() is not None


# =========================
# 获取某个聊天里的所有消息
# =========================

def get_messages(session_id, user_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                cm.user_message,
                cm.ai_message
            FROM chat_messages cm
            JOIN chat_sessions cs
                ON cm.session_id = cs.id
            WHERE cm.session_id = %s
              AND cs.user_id = %s
            ORDER BY cm.id ASC
            """,
            (
                session_id,
                user_id
            )
        )

        messages = cursor.fetchall()

    return messages


# =========================
# 修改聊天标题
# =========================

def update_session_title(session_id, title, user_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE chat_sessions
            SET title = %s
            WHERE id = %s
              AND user_id = %s
            """,
            (
                title,
                session_id,
                user_id
            )
        )

    connection.commit()


# =========================
# 删除一个聊天会话
# =========================

def delete_session(session_id, user_id):
    with connection.cursor() as cursor:

        # 删除当前用户自己的聊天消息
        cursor.execute(
            """
            DELETE FROM chat_messages
            WHERE session_id = %s
              AND session_id IN (
                  SELECT id
                  FROM chat_sessions
                  WHERE id = %s
                    AND user_id = %s
              )
            """,
            (
                session_id,
                session_id,
                user_id
            )
        )

        # 删除当前用户自己的聊天会话
        cursor.execute(
            """
            DELETE FROM chat_sessions
            WHERE id = %s
              AND user_id = %s
            """,
            (
                session_id,
                user_id
            )
        )

    connection.commit()


# =========================
# 保存知识库文档
# =========================

def save_document(
    user_id,
    content,
    embedding,
    filename,
    page_number,
    chunk_id
):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO documents
            (
                user_id,
                content,
                embedding,
                filename,
                page_number,
                chunk_id
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                content,
                embedding,
                filename,
                page_number,
                chunk_id
            )
        )

    connection.commit()


# =========================
# 向量相似度搜索
# =========================

def search_similar(
    embedding,
    user_id,
    top_k=3
):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                content,
                embedding <=> %s AS distance
            FROM documents
            WHERE user_id = %s
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (
                embedding,
                user_id,
                embedding,
                top_k
            )
        )

        results = cursor.fetchall()

    return results


# =========================
# 获取当前用户的知识库文件列表
# =========================

def get_documents(user_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                filename,
                COUNT(*) AS chunk_count
            FROM documents
            WHERE user_id = %s
            GROUP BY filename
            ORDER BY filename
            """,
            (user_id,)
        )

        documents = cursor.fetchall()

    return documents


# =========================
# 检查当前用户是否已经上传该文件
# =========================

def check_document_exists(filename, user_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM documents
            WHERE filename = %s
              AND user_id = %s
            """,
            (
                filename,
                user_id
            )
        )

        count = cursor.fetchone()[0]

    return count > 0


# =========================
# 删除当前用户的 PDF 文档
# =========================

def delete_document(filename, user_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM documents
            WHERE filename = %s
              AND user_id = %s
            """,
            (
                filename,
                user_id
            )
        )

    connection.commit()


# =========================
# 向量搜索
# =========================

def search_documents(
    query_embedding,
    user_id,
    top_k=3
):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                content,
                filename,
                page_number,
                chunk_id
            FROM documents
            WHERE embedding IS NOT NULL
              AND user_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (
                user_id,
                str(query_embedding),
                top_k
            )
        )

        results = cursor.fetchall()

    return results


# =========================
# 关键词搜索
# =========================

def keyword_search_documents(
    query,
    user_id,
    top_k=3
):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                content,
                filename,
                page_number,
                chunk_id
            FROM documents
            WHERE user_id = %s
              AND to_tsvector('simple', content)
              @@ plainto_tsquery('simple', %s)
            LIMIT %s
            """,
            (
                user_id,
                query,
                top_k
            )
        )

        results = cursor.fetchall()

    return results


# =========================
# Hybrid Search
# =========================

def hybrid_search_documents(
    query,
    query_embedding,
    user_id,
    top_k=3
):

    # 1. 向量检索
    vector_results = search_documents(
        query_embedding,
        user_id,
        top_k=10
    )

    # 2. 关键词检索
    keyword_results = keyword_search_documents(
        query,
        user_id,
        top_k=10
    )

    # 3. 加权融合
    scores = {}

    vector_weight = 0.7
    keyword_weight = 0.3

    # =========================
    # 向量检索排名计分
    # =========================

    for rank, result in enumerate(
        vector_results,
        start=1
    ):

        content, filename, page_number, chunk_id = result

        score = vector_weight / rank

        scores[content] = {
            "content": content,
            "score": score,
            "filename": filename,
            "page_number": page_number,
            "chunk_id": chunk_id
        }

    # =========================
    # 关键词检索排名计分
    # =========================

    for rank, result in enumerate(
        keyword_results,
        start=1
    ):

        content, filename, page_number, chunk_id = result

        score = keyword_weight / rank

        if content in scores:

            scores[content]["score"] += score

        else:

            scores[content] = {
                "content": content,
                "score": score,
                "filename": filename,
                "page_number": page_number,
                "chunk_id": chunk_id
            }

    # =========================
    # 按最终分数排序
    # =========================

    sorted_results = sorted(
        scores.values(),
        key=lambda x: x["score"],
        reverse=True
    )

    # =========================
    # 返回最终结果
    # =========================

    return [
        (
            item["content"],
            item["filename"],
            item["page_number"],
            item["chunk_id"]
        )
        for item in sorted_results[:top_k]
    ]


# =========================
# 用户注册
# =========================

def create_user(username, password_hash):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO users
            (username, password_hash)
            VALUES (%s, %s)
            RETURNING id
            """,
            (
                username,
                password_hash
            )
        )

        user_id = cursor.fetchone()[0]

    connection.commit()

    return user_id


# =========================
# 根据用户名查询用户
# =========================

def get_user_by_username(username):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                username,
                password_hash
            FROM users
            WHERE username = %s
            """,
            (username,)
        )

        return cursor.fetchone()