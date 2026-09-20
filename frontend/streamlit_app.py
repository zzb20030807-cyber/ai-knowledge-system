import streamlit as st
import requests


BACKEND_URL = "http://127.0.0.1:8000"


st.set_page_config(
    page_title="AI 智能问答系统",
    page_icon="🤖",
    layout="wide"
)


st.title("🤖 AI 智能问答系统")


# =========================
# 创建聊天
# =========================

def create_new_session():

    response = requests.post(
        f"{BACKEND_URL}/session",
        json={"title": "新聊天"}
    )

    response.raise_for_status()

    return response.json()["session_id"]


# =========================
# 获取历史聊天
# =========================

def get_sessions():

    response = requests.get(
        f"{BACKEND_URL}/sessions"
    )

    response.raise_for_status()

    return response.json()["sessions"]


# =========================
# 获取聊天消息
# =========================

def get_messages(session_id):

    response = requests.get(
        f"{BACKEND_URL}/sessions/{session_id}/messages"
    )

    response.raise_for_status()

    return response.json()["messages"]


# =========================
# 删除聊天
# =========================

def delete_session(session_id):

    response = requests.delete(
        f"{BACKEND_URL}/sessions/{session_id}"
    )

    response.raise_for_status()


# =========================
# 获取知识库文档
# =========================

def get_documents():

    response = requests.get(
        f"{BACKEND_URL}/documents"
    )

    response.raise_for_status()

    return response.json()["documents"]


# =========================
# 删除知识库文档
# =========================

def delete_document(filename):

    response = requests.delete(
        f"{BACKEND_URL}/documents/{filename}"
    )

    response.raise_for_status()


# =========================
# 上传知识库文档
# =========================

def upload_document(uploaded_file):

    response = requests.post(
        f"{BACKEND_URL}/upload",
        files={
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                "application/pdf"
            )
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json()


# =========================
# 初始化 Session State
# =========================

if "session_id" not in st.session_state:

    sessions = get_sessions()

    if sessions:

        st.session_state.session_id = sessions[0][0]

        old_messages = get_messages(
            st.session_state.session_id
        )

        st.session_state.messages = []

        for message in old_messages:

            st.session_state.messages.append(
                {
                    "role": "user",
                    "content": message[0]
                }
            )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": message[1]
                }
            )

    else:

        st.session_state.session_id = create_new_session()

        st.session_state.messages = []


if "messages" not in st.session_state:

    st.session_state.messages = []


# =========================
# 左侧边栏
# =========================

with st.sidebar:

    st.header("💬 聊天记录")


    # 新建聊天

    if st.button(
        "＋ 新聊天",
        use_container_width=True
    ):

        st.session_state.session_id = create_new_session()

        st.session_state.messages = []

        st.rerun()


    st.divider()


    # =========================
    # 历史会话
    # =========================

    sessions = get_sessions()


    for session in sessions:

        session_id = session[0]
        title = session[1]


        col1, col2 = st.columns([5, 1])


        with col1:

            if st.button(
                title,
                key=f"session_{session_id}",
                use_container_width=True
            ):

                st.session_state.session_id = session_id

                old_messages = get_messages(
                    session_id
                )

                st.session_state.messages = []


                for message in old_messages:

                    st.session_state.messages.append(
                        {
                            "role": "user",
                            "content": message[0]
                        }
                    )

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": message[1]
                        }
                    )


                st.rerun()


        with col2:

            if st.button(
                "🗑️",
                key=f"delete_{session_id}"
            ):

                delete_session(session_id)


                if st.session_state.session_id == session_id:

                    st.session_state.session_id = None

                    st.session_state.messages = []


                st.rerun()


    st.divider()


    # =========================
    # 知识库管理
    # =========================

    st.header("📚 知识库")


    uploaded_file = st.file_uploader(
        "上传PDF",
        type=["pdf"]
    )


    if uploaded_file is not None:

        if st.button(
            "上传到知识库",
            use_container_width=True
        ):

            try:

                result = upload_document(
                    uploaded_file
                )

                if "message" in result:

                    st.warning(
                        result["message"]
                    )

                else:

                    st.success(
                        f"上传成功：{result['filename']}"
                    )

                    st.write(
                        f"页数：{result['pages']}"
                    )

                    st.write(
                        f"Chunk数量：{result['chunk_count']}"
                    )

                    st.rerun()

            except requests.exceptions.RequestException as e:

                st.error(
                    f"上传失败：{e}"
                )


    # =========================
    # 文档列表
    # =========================

    try:

        documents = get_documents()


        for document in documents:

            filename = document[0]
            chunk_count = document[1]


            st.write(
                f"📄 {filename}"
            )

            st.caption(
                f"{chunk_count} 个 Chunk"
            )


            if st.button(
                "删除",
                key=f"delete_doc_{filename}",
                use_container_width=True
            ):

                delete_document(filename)

                st.success("文档已删除")

                st.rerun()


    except requests.exceptions.RequestException:

        st.warning(
            "知识库接口暂时不可用"
        )


# =========================
# 显示历史消息
# =========================

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.write(
            message["content"]
        )


# =========================
# 用户输入
# =========================

question = st.chat_input(
    "请输入你的问题"
)


if question:

    # 如果当前没有session
    if st.session_state.session_id is None:

        st.session_state.session_id = (
            create_new_session()
        )


    # 显示用户问题

    with st.chat_message("user"):

        st.write(question)


    try:

        # =========================
        # 请求FastAPI
        # =========================

        response = requests.post(
            f"{BACKEND_URL}/chat",

            json={
                "message": question,
                "session_id":
                    st.session_state.session_id
            },

            stream=True,

            timeout=120
        )


        response.raise_for_status()


        # =========================
        # 流式数据生成器
        # =========================

        def response_generator():

            for chunk in response.iter_content(
                chunk_size=None,
                decode_unicode=True
            ):

                if chunk:

                    yield chunk


        # =========================
        # 显示AI回答
        # =========================

        with st.chat_message(
            "assistant"
        ):

            full_response = st.write_stream(
                response_generator()
            )


        # =========================
        # 保存到前端状态
        # =========================

        st.session_state.messages.append(
            {
                "role": "user",
                "content": question
            }
        )


        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": full_response
            }
        )


    except requests.exceptions.RequestException as e:

        st.error(
            f"请求后端失败：{e}"
        )