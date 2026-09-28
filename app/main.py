from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Depends
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token
)

from pypdf import PdfReader
from io import BytesIO

from app.embedding import get_embeddings
from app.services.qwen_services import ask_qwen

from app.database import (
    save_message,
    create_session,
    get_sessions,
    get_messages,
    update_session_title,
    delete_session,
    check_session_owner,
    save_document,
    hybrid_search_documents,
    get_documents,
    delete_document,
    check_document_exists,
    create_user,
    get_user_by_username
)

from app.rerank import rerank_documents
from langchain_text_splitters import RecursiveCharacterTextSplitter


app = FastAPI()

security = HTTPBearer()


# =========================
# 数据模型
# =========================

class ChatRequest(BaseModel):
    message: str
    session_id: int


class SessionRequest(BaseModel):
    title: str = "新聊天"


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


# =========================
# JWT 获取当前用户
# =========================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    try:
        payload = decode_access_token(token)

    except ValueError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )

    user_id = payload.get("user_id")
    username = payload.get("username")

    if not user_id or not username:
        raise HTTPException(
            status_code=401,
            detail="Token 信息不完整"
        )

    return {
        "user_id": user_id,
        "username": username
    }


# =========================
# 根路径
# =========================

@app.get("/")
def read_root():
    return {
        "message": "AI 智能问答系统-v.1.0"
    }


# =========================
# 用户注册
# =========================

@app.post("/register")
def register(request: RegisterRequest):

    username = request.username.strip()

    if not username:
        raise HTTPException(
            status_code=400,
            detail="用户名不能为空"
        )

    # 检查用户名是否已经存在
    existing_user = get_user_by_username(username)

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="用户名已存在"
        )

    # 密码哈希
    password_hash = hash_password(
        request.password
    )

    # 保存用户
    user_id = create_user(
        username,
        password_hash
    )

    return {
        "message": "注册成功",
        "user_id": user_id,
        "username": username
    }


# =========================
# 用户登录
# =========================

@app.post("/login")
def login(request: LoginRequest):

    username = request.username.strip()

    if not username:
        raise HTTPException(
            status_code=400,
            detail="用户名不能为空"
        )

    # 根据用户名查询用户
    user = get_user_by_username(username)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误"
        )

    user_id, db_username, password_hash = user

    # 验证密码
    if not verify_password(
        request.password,
        password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误"
        )

    # 生成 JWT
    access_token = create_access_token(
        user_id=user_id,
        username=db_username
    )

    return {
        "message": "登录成功",
        "user_id": user_id,
        "username": db_username,
        "access_token": access_token,
        "token_type": "bearer"
    }


# =========================
# 创建聊天
# =========================

@app.post("/session")
def create_chat_session(
    request: SessionRequest,
    current_user=Depends(get_current_user)
):
    user_id = current_user["user_id"]

    session_id = create_session(
        user_id=user_id,
        title=request.title
    )

    return {
        "session_id": session_id,
        "title": request.title
    }


# =========================
# 获取当前用户的聊天
# =========================

@app.get("/sessions")
def list_sessions(
    current_user=Depends(get_current_user)
):
    user_id = current_user["user_id"]

    sessions = get_sessions(
        user_id
    )

    return [
        {
            "id": session[0],
            "title": session[1]
        }
        for session in sessions
    ]


# =========================
# 获取某个聊天的消息
# =========================

@app.get("/sessions/{session_id}/messages")
def get_session_messages(
    session_id: int,
    current_user=Depends(get_current_user)
):
    user_id = current_user["user_id"]

    if not check_session_owner(
        session_id,
        user_id
    ):
        raise HTTPException(
            status_code=403,
            detail="无权访问该聊天会话"
        )

    messages = get_messages(
        session_id,
        user_id
    )


# =========================
# 删除聊天
# =========================

@app.delete("/sessions/{session_id}")
def remove_session(
    session_id: int,
    current_user=Depends(get_current_user)
):
    user_id = current_user["user_id"]

    delete_session(
        session_id,
        user_id
    )

    return {
        "message": "删除成功"
    }


# =========================
# AI聊天
# =========================

@app.post("/chat")
def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user)
):

    # 当前登录用户
    user_id = current_user["user_id"]

    # 检查这个聊天会话是不是当前用户自己的
    if not check_session_owner(
        request.session_id,
        user_id
    ):
        raise HTTPException(
            status_code=403,
            detail="无权访问该聊天会话"
        )

    print(
        "收到请求",
        request.message
    )

    # 保存完整AI回答
    full_response = ""

    # =========================
    # ① 用户问题转换成向量
    # =========================

    query_vector = get_embeddings(
        [request.message]
    )[0]

    # =========================
    # ② Hybrid Search召回候选文档
    # =========================

    results = hybrid_search_documents(
        request.message,
        query_vector,
        top_k=10
    )

    print(
        "===== Hybrid Search结果 ====="
    )

    for i, result in enumerate(results):
        print(
            f"第{i+1}条:",
            result[0][:100]
        )

    # =========================
    # ③ 提取文本内容给Rerank
    # =========================

    documents = [
        result[0]
        for result in results
    ]

    # =========================
    # ④ Rerank重新排序
    # =========================

    reranked_docs = rerank_documents(
        request.message,
        documents,
        top_k=3
    )

    print(
        "===== Rerank结果 ====="
    )

    for i, doc in enumerate(reranked_docs):
        print(
            f"第{i+1}条:",
            doc[:100]
        )

    # =========================
    # ⑤ 拼接最终知识上下文
    # =========================

    context = "\n\n".join(
        reranked_docs
    )

    # 建立“内容 -> 来源信息”的对应关系
    result_map = {
        result[0]: result
        for result in results
    }

    # 只显示Rerank后的Top3来源
    sources = "\n".join(
        [
            f"- {result_map[doc][1]} "
            f"第{result_map[doc][2]}页 "
            f"chunk_{result_map[doc][3]}"
            for doc in reranked_docs
            if doc in result_map
        ]
    )

    # 给大模型的完整上下文
    rag_context = f"""
知识库内容：

{context}

知识来源：

{sources}
"""

    print(
        "🔍 用户问题：",
        request.message
    )

    print(
        "📚 Rerank后的知识："
    )

    print(context)

    print(
        "📄 知识来源："
    )

    print(sources)

    # =========================
    # ⑥ 流式生成回答
    # =========================

    def generate():

        nonlocal full_response

        # 调用Qwen
        for chunk in ask_qwen(
            request.message,
            rag_context
        ):

            # 返回前端
            yield chunk

            # 保存完整回答
            full_response += chunk

        # 添加参考来源
        source_text = (
            "\n\n📚 参考来源：\n"
            + sources
        )

        yield source_text

        full_response += source_text

        # =========================
        # ⑦ 保存聊天记录
        # =========================

        save_message(
            request.message,
            full_response,
            request.session_id
        )

        # =========================
        # ⑧ 第一条消息自动生成标题
        # =========================

        messages = get_messages(
            request.session_id,
            user_id
        )

        if len(messages) == 1:

            title = request.message[:30]

            update_session_title(
                request.session_id,
                title,
                user_id
            )

    # =========================
    # ⑨ 流式返回
    # =========================

    return StreamingResponse(
        generate(),
        media_type="text/plain"
    )


# =========================
# 文本切分函数
# =========================

def split_text(text):

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50,
        separators=[
            "\n\n",
            "\n",
            "。",
            "!",
            "?",
            ",",
            " "
        ]
    )

    chunks = splitter.split_text(
        text
    )

    return chunks


# =========================
# PDF上传接口
# =========================

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...)
):

    # 检查文件是否已经存在
    if check_document_exists(
        file.filename
    ):

        return {
            "message": "该文件已经存在，请勿重复上传",
            "filename": file.filename
        }

    # 判断是不是 PDF
    if file.content_type != "application/pdf":

        return {
            "error": "目前只支持 PDF 文件"
        }

    # 读取上传文件
    contents = await file.read()

    # 读取 PDF
    pdf = PdfReader(
        BytesIO(contents)
    )

    # 保存每一页文本
    pages_text = []

    # 按页读取PDF
    for page_number, page in enumerate(
        pdf.pages,
        start=1
    ):

        page_text = page.extract_text()

        if page_text:

            pages_text.append(
                (
                    page_number,
                    page_text
                )
            )

    # =========================
    # 文本切片
    # =========================

    all_chunks = []

    for page_number, page_text in pages_text:

        chunks = split_text(
            page_text
        )

        for chunk_id, chunk in enumerate(
            chunks,
            start=1
        ):

            all_chunks.append(
                {
                    "content": chunk,
                    "page_number": page_number,
                    "chunk_id": chunk_id
                }
            )

    # =========================
    # Embedding
    # =========================

    texts = [
        item["content"]
        for item in all_chunks
    ]

    vectors = get_embeddings(
        texts
    )

    # =========================
    # 保存数据库
    # =========================

    for item, vector in zip(
        all_chunks,
        vectors
    ):

        save_document(
            item["content"],
            vector,
            file.filename,
            item["page_number"],
            item["chunk_id"]
        )

    # =========================
    # 返回结果
    # =========================

    return {
        "filename": file.filename,
        "pages": len(pdf.pages),
        "chunk_count": len(all_chunks),
        "chunks": [
            item["content"]
            for item in all_chunks
        ]
    }


# =========================
# 获取知识库文件列表
# =========================

@app.get("/documents")
def documents():

    docs = get_documents()

    return {
        "documents": docs
    }


# =========================
# 删除知识库文件
# =========================

@app.delete("/documents/{filename}")
def remove_document(
    filename: str
):

    delete_document(
        filename
    )

    return {
        "message": "删除成功",
        "filename": filename
    }


# =========================
# 当前登录用户
# =========================

@app.get("/me")
def get_me(
    current_user=Depends(get_current_user)
):
    return {
        "message": "身份验证成功",
        "user_id": current_user["user_id"],
        "username": current_user["username"]
    }