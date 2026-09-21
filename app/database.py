import os
import psycopg
from pgvector.psycopg import register_vector

# 连接 PostgreSQL 数据库
connection = psycopg.connect(
    host=os.getenv("DB_HOST","127.0.0.1"),
    port=int(os.getenv("DB_PORT", "5432")),
    dbname=os.getenv("DB_NAME", "ai_knowledge"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD"),
    autocommit=True
)
register_vector(connection)

# 保存聊天记录
def save_message(user_message, ai_message, session_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat_messages
            (user_message, ai_message, session_id)
            VALUES (%s, %s, %s)
            """,
            (user_message, ai_message, session_id)
        )

    connection.commit()


# 创建新的聊天
def create_session(title="新聊天"):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat_sessions (title)
            VALUES (%s)
            RETURNING id
            """,
            (title,)
        )

        session_id = cursor.fetchone()[0]

    connection.commit()

    return session_id


# 🟢 新增：查询所有聊天会话
def get_sessions():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, title
            FROM chat_sessions
            ORDER BY created_at DESC
            """
        )

        sessions = cursor.fetchall()

    return sessions


# 🟢 新增：查询某一个聊天里的所有消息
def get_messages(session_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT user_message, ai_message
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY id ASC
            """,
            (session_id,)
        )

        messages = cursor.fetchall()

    return messages

# 🟢 新增：修改聊天标题
def update_session_title(session_id, title):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE chat_sessions
            SET title = %s
            WHERE id = %s
            """,
            (title, session_id)
        )

    connection.commit()


print("数据库连接成功！")

# 🟢 新增：删除一个聊天会话
def delete_session(session_id):
    with connection.cursor() as cursor:

        # 先删除这个聊天里的所有消息
        cursor.execute(
            """
            DELETE FROM chat_messages
            WHERE session_id = %s
            """,
            (session_id,)
        )

        # 再删除聊天本身
        cursor.execute(
            """
            DELETE FROM chat_sessions
            WHERE id = %s
            """,
            (session_id,)
        )

    connection.commit()



def save_document(
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
            (content, embedding, filename, page_number, chunk_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                content,
                embedding,
                filename,
                page_number,
                chunk_id
            )
        )

    connection.commit()
    def search_similar(embedding, top_k=3):
        with connection.cursor() as cursor:
            cursor.execute(
            """
            SELECT content, embedding <=> %s AS distance
            FROM documents
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (embedding, embedding, top_k)
        )

        results = cursor.fetchall()

        return results
# 获取知识库文件列表
def get_documents():

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT 
                filename,
                COUNT(*) as chunk_count
            FROM documents
            GROUP BY filename
            ORDER BY filename
            """
        )

        documents = cursor.fetchall()

    return documents

def check_document_exists(filename):

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM documents
            WHERE filename = %s
            """,
            (filename,)
        )

        count = cursor.fetchone()[0]

    return count > 0



# 删除整个PDF文档
def delete_document(filename):

    with connection.cursor() as cursor:

        cursor.execute(
            """
            DELETE FROM documents
            WHERE filename = %s
            """,
            (filename,)
        )

    connection.commit()

def search_documents(query_embedding, top_k=3):

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

            ORDER BY embedding <=> %s::vector

            LIMIT %s
            """,

            (
                str(query_embedding),
                top_k
            )
        )


        results = cursor.fetchall()


    return results

def keyword_search_documents(query, top_k=3):

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT
                content,
                filename,
                page_number,
                chunk_id

            FROM documents

            WHERE to_tsvector('simple', content)
            @@ plainto_tsquery('simple', %s)

            LIMIT %s
            """,

            (
                query,
                top_k
            )
        )


        results = cursor.fetchall()


    return results

def hybrid_search_documents(query, query_embedding, top_k=3):

    # 1. 向量检索
    vector_results = search_documents(
        query_embedding,
        top_k=10
    )

    # 2. 关键词检索
    keyword_results = keyword_search_documents(
        query,
        top_k=10
    )

    # 3. 加权融合
    scores = {}

    vector_weight = 0.7
    keyword_weight = 0.3

    # 向量检索排名计分
    for rank, result in enumerate(vector_results, start=1):

        content, filename, page_number, chunk_id = result

        score = vector_weight / rank

        scores[content] = {
            "content": content,
            "score": score,
            "filename": filename,
            "page_number": page_number,
            "chunk_id": chunk_id
        }

    # 关键词检索排名计分
    for rank, result in enumerate(keyword_results, start=1):

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

    # 4. 按最终分数排序
    sorted_results = sorted(
        scores.values(),
        key=lambda x: x["score"],
        reverse=True
    )

    # 5. 返回最终结果
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
            INSERT INTO users (username, password_hash)
            VALUES (%s, %s)
            RETURNING id
            """,
            (username, password_hash)
        )

        user_id = cursor.fetchone()[0]

    connection.commit()

    return user_id


# 根据用户名查询用户
def get_user_by_username(username):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, password_hash
            FROM users
            WHERE username = %s
            """,
            (username,)
        )

        return cursor.fetchone()