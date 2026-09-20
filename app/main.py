from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pypdf import PdfReader
from io import BytesIO
from app.embedding import get_embeddings
from app.database import save_document
from app.services.qwen_services import ask_qwen
from app.embedding import get_embeddings
from app.database import search_documents
from app.database import (
    save_message,
    create_session,
    get_sessions,
    get_messages,
    update_session_title,
    delete_session,
    save_document,
    hybrid_search_documents,
    get_documents,
    delete_document,
    check_document_exists
)
from app.rerank import rerank_documents
from langchain_text_splitters import RecursiveCharacterTextSplitter

app = FastAPI()



class ChatRequest(BaseModel):
    message: str
    session_id: int


class SessionRequest(BaseModel):
    title: str = "新聊天"


@app.get("/")
def read_root():
    return {"message": "AI 智能问答系统-v.1.0"}


# 创建聊天
@app.post("/session")
def create_chat_session(request: SessionRequest):

    session_id = create_session(request.title)

    return {"session_id": session_id}


# 获取所有历史聊天
@app.get("/sessions")
def get_chat_sessions():

    print("🔵 开始获取聊天记录")

    try:

        sessions = get_sessions()

        print("🟢 获取聊天记录成功：", sessions)

        return {
            "sessions": sessions
        }

    except Exception as e:

        print("🔴 获取聊天记录失败：", repr(e))

        raise

# 获取某个聊天的消息
@app.get("/sessions/{session_id}/messages")
def get_chat_messages(session_id: int):

    messages = get_messages(session_id)

    return {
        "messages": messages
    }


# 删除聊天
@app.delete("/sessions/{session_id}")
def delete_chat_session(session_id: int):

    delete_session(session_id)

    return {
        "message": "聊天删除成功"
    }


# 🟡 修改：聊天接口改成流式返回
@app.post("/chat")
def chat(request: ChatRequest):

    print("收到请求", request.message)

    # 保存完整AI回答
    full_response = ""


    # ① 用户问题转换成向量
    query_vector = get_embeddings(
        [request.message]
    )[0]


    # ② Hybrid Search召回候选文档
    # 先找10条候选
    results = hybrid_search_documents(
        request.message,
        query_vector,
        top_k=10
    )


    print("===== Hybrid Search结果 =====")

    for i, result in enumerate(results):
        print(
            f"第{i+1}条:",
            result[0][:100]
        )


    # ③ 提取文本内容给Rerank
    documents = [
        result[0]
        for result in results
    ]


    # ④ Rerank重新排序
    # 从10条里面选最相关3条
    reranked_docs = rerank_documents(
        request.message,
        documents,
        top_k=3
    )


    print("===== Rerank结果 =====")

    for i, doc in enumerate(reranked_docs):
        print(
            f"第{i+1}条:",
            doc[:100]
        )


    # ⑤ 拼接最终知识上下文
    # 建立“内容 -> 来源信息”的对应关系
# ⑤ 拼接最终知识上下文
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
            f"- {result_map[doc][1]} 第{result_map[doc][2]}页 chunk_{result_map[doc][3]}"
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


    print("🔍 用户问题：", request.message)

    print("📚 Rerank后的知识：")
    print(context)

    print("📄 知识来源：")
    print(sources)



    # ⑥ 流式生成回答
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



        # ⑦ 保存聊天记录
        save_message(
            request.message,
            full_response,
            request.session_id
        )



        # ⑧ 第一条消息自动生成标题
        messages = get_messages(
            request.session_id
        )


        if len(messages) == 1:

            title = request.message[:30]


            update_session_title(
                request.session_id,
                title
            )



    # ⑨ 流式返回
    return StreamingResponse(
        generate(),
        media_type="text/plain"
    )

# 上传 PDF 文档
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

    chunks = splitter.split_text(text)

    return chunks


# =========================
# PDF上传接口
# =========================
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
# 检查文件是否已经存在

    if check_document_exists(file.filename):

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
    for page_number, page in enumerate(pdf.pages, start=1):

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


        for chunk_id, chunk in enumerate(chunks, start=1):


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

    for item, vector in zip(all_chunks, vectors):


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
def remove_document(filename: str):

    delete_document(filename)

    return {
        "message": "删除成功",
        "filename": filename
    }