from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Depends,
    Request
)
from fastapi.responses import (
    StreamingResponse,
    JSONResponse
)
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)
from fastapi.exceptions import RequestValidationError

from pydantic import BaseModel, Field
from fastapi.encoders import jsonable_encoder

from pypdf import PdfReader
from io import BytesIO

from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token
)

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
from app.logger import logger

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)


# =========================
# FastAPI
# =========================

app = FastAPI()

security = HTTPBearer()


# =========================
# 请求日志中间件
# =========================

@app.middleware("http")
async def log_requests(
    request: Request,
    call_next
):
    import time

    start_time = time.time()

    try:

        response = await call_next(request)

    except Exception:

        logger.exception(
            "%s %s | 未处理异常",
            request.method,
            request.url.path
        )

        raise

    process_time = time.time() - start_time

    logger.info(
        "%s %s -> %s (%.3fs)",
        request.method,
        request.url.path,
        response.status_code,
        process_time
    )

    return response


# =========================
# HTTP 异常统一处理
# =========================

@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException
):

    logger.warning(
        "%s %s -> %s | %s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail
        }
    )


# =========================
# 参数验证异常
# =========================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):

    logger.warning(
        "%s %s -> 422 | 参数验证失败",
        request.method,
        request.url.path
    )

    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "请求参数错误",
            "details": jsonable_encoder(
                exc.errors()
            )
        }
    )


# =========================
# 未处理异常
# =========================

@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception
):

    logger.exception(
        "%s %s -> 500 | 未处理异常",
        request.method,
        request.url.path
    )

    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误"
        }
    )


# =========================
# 数据模型
# =========================

class ChatRequest(BaseModel):
    message: str
    session_id: int


class SessionRequest(BaseModel):
    title: str = "新聊天"


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50
    )

    password: str = Field(
        min_length=6,
        max_length=128
    )


class LoginRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50
    )

    password: str = Field(
        min_length=6,
        max_length=128
    )


# =========================
# JWT 获取当前用户
# =========================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    )
):

    token = credentials.credentials

    try:

        payload = decode_access_token(
            token
        )

    except ValueError as e:

        raise HTTPException(
            status_code=401,
            detail=str(e)
        )

    user_id = payload.get(
        "user_id"
    )

    username = payload.get(
        "username"
    )

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
def register(
    request: RegisterRequest
):

    username = request.username.strip()

    if not username:

        raise HTTPException(
            status_code=400,
            detail="用户名不能为空"
        )

    existing_user = get_user_by_username(
        username
    )

    if existing_user:

        raise HTTPException(
            status_code=409,
            detail="用户名已存在"
        )

    password_hash = hash_password(
        request.password
    )

    user_id = create_user(
        username,
        password_hash
    )

    logger.info(
        "用户注册成功 | user_id=%s | username=%s",
        user_id,
        username
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
def login(
    request: LoginRequest
):

    username = request.username.strip()

    if not username:

        raise HTTPException(
            status_code=400,
            detail="用户名不能为空"
        )

    user = get_user_by_username(
        username
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误"
        )

    user_id, db_username, password_hash = user

    if not verify_password(
        request.password,
        password_hash
    ):

        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误"
        )

    access_token = create_access_token(
        user_id=user_id,
        username=db_username
    )

    logger.info(
        "用户登录成功 | user_id=%s | username=%s",
        user_id,
        db_username
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
    current_user=Depends(
        get_current_user
    )
):

    user_id = current_user[
        "user_id"
    ]

    session_id = create_session(
        user_id=user_id,
        title=request.title
    )

    logger.info(
        "创建聊天成功 | user_id=%s | session_id=%s",
        user_id,
        session_id
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
    current_user=Depends(
        get_current_user
    )
):

    user_id = current_user[
        "user_id"
    ]

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

@app.get(
    "/sessions/{session_id}/messages"
)
def get_session_messages(
    session_id: int,
    current_user=Depends(
        get_current_user
    )
):

    user_id = current_user[
        "user_id"
    ]

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

    return [
        {
            "user_message": message[0],
            "ai_message": message[1]
        }
        for message in messages
    ]


# =========================
# 删除聊天
# =========================

@app.delete(
    "/sessions/{session_id}"
)
def remove_session(
    session_id: int,
    current_user=Depends(
        get_current_user
    )
):

    user_id = current_user[
        "user_id"
    ]

    if not check_session_owner(
        session_id,
        user_id
    ):

        raise HTTPException(
            status_code=403,
            detail="无权访问该聊天会话"
        )

    delete_session(
        session_id,
        user_id
    )

    logger.info(
        "删除聊天成功 | user_id=%s | session_id=%s",
        user_id,
        session_id
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
    current_user=Depends(
        get_current_user
    )
):

    user_id = current_user[
        "user_id"
    ]

    # 检查聊天会话归属
    if not check_session_owner(
        request.session_id,
        user_id
    ):

        raise HTTPException(
            status_code=403,
            detail="无权访问该聊天会话"
        )

    logger.info(
        "收到聊天请求 | user_id=%s | session_id=%s",
        user_id,
        request.session_id
    )

    # 保存完整 AI 回答
    full_response = ""

    # =========================
    # ① 用户问题转换成向量
    # =========================

    query_vector = get_embeddings(
        [request.message]
    )[0]

    # =========================
    # ② 当前用户知识库 Hybrid Search
    # =========================

    results = hybrid_search_documents(
        request.message,
        query_vector,
        user_id,
        top_k=10
    )

    logger.info(
        "Hybrid Search完成 | user_id=%s | results=%s",
        user_id,
        len(results)
    )

    # =========================
    # ③ 提取文本
    # =========================

    documents = [
        result[0]
        for result in results
    ]

    # =========================
    # ④ Rerank
    # =========================

    reranked_docs = rerank_documents(
        request.message,
        documents,
        top_k=3
    )

    logger.info(
        "Rerank完成 | user_id=%s | results=%s",
        user_id,
        len(reranked_docs)
    )

    # =========================
    # ⑤ 拼接知识上下文
    # =========================

    context = "\n\n".join(
        reranked_docs
    )

    result_map = {
        result[0]: result
        for result in results
    }

    sources = "\n".join(
        [
            f"- {result_map[doc][1]} "
            f"第{result_map[doc][2]}页 "
            f"chunk_{result_map[doc][3]}"
            for doc in reranked_docs
            if doc in result_map
        ]
    )

    rag_context = f"""
知识库内容：

{context}

知识来源：

{sources}
"""

    logger.info(
        "RAG检索完成 | user_id=%s | session_id=%s | sources=%s",
        user_id,
        request.session_id,
        len(reranked_docs)
    )

    # =========================
    # ⑥ 流式生成
    # =========================

    def generate():

        nonlocal full_response

        for chunk in ask_qwen(
            request.message,
            rag_context
        ):

            yield chunk

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

        logger.info(
            "聊天记录保存成功 | user_id=%s | session_id=%s",
            user_id,
            request.session_id
        )

        # =========================
        # ⑧ 自动生成标题
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

            logger.info(
                "聊天标题更新 | user_id=%s | session_id=%s",
                user_id,
                request.session_id
            )

    # =========================
    # ⑨ 流式返回
    # =========================

    return StreamingResponse(
        generate(),
        media_type="text/plain"
    )


# =========================
# 文本切分
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
# PDF上传
# =========================

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user=Depends(
        get_current_user
    )
):

    user_id = current_user[
        "user_id"
    ]

    # 检查当前用户是否已经上传过
    if check_document_exists(
        file.filename,
        user_id
    ):

        return {
            "message": "该文件已经存在，请勿重复上传",
            "filename": file.filename
        }

    # 判断 PDF
    if file.content_type != "application/pdf":

        raise HTTPException(
            status_code=400,
            detail="目前只支持 PDF 文件"
        )

    # 读取文件
    contents = await file.read()

    # PDF
    pdf = PdfReader(
        BytesIO(contents)
    )

    # 保存每页文本
    pages_text = []

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
            user_id,
            item["content"],
            vector,
            file.filename,
            item["page_number"],
            item["chunk_id"]
        )

    logger.info(
        "知识库上传成功 | user_id=%s | filename=%s | chunks=%s",
        user_id,
        file.filename,
        len(all_chunks)
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
# 获取当前用户的知识库
# =========================

@app.get("/documents")
def documents(
    current_user=Depends(
        get_current_user
    )
):

    user_id = current_user[
        "user_id"
    ]

    docs = get_documents(
        user_id
    )

    return {
        "documents": docs
    }


# =========================
# 删除当前用户的知识库文件
# =========================

@app.delete(
    "/documents/{filename}"
)
def remove_document(
    filename: str,
    current_user=Depends(
        get_current_user
    )
):

    user_id = current_user[
        "user_id"
    ]

    # 检查当前用户是否拥有该文件
    if not check_document_exists(
        filename,
        user_id
    ):

        raise HTTPException(
            status_code=404,
            detail="文件不存在"
        )

    delete_document(
        filename,
        user_id
    )

    logger.info(
        "知识库删除成功 | user_id=%s | filename=%s",
        user_id,
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
    current_user=Depends(
        get_current_user
    )
):

    return {
        "message": "身份验证成功",
        "user_id": current_user["user_id"],
        "username": current_user["username"]
    }
