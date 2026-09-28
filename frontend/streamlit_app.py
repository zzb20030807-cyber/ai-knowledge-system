
import streamlit as st
import requests
from urllib.parse import quote


# =========================================================
# 基础配置
# =========================================================

BACKEND_URL = "http://127.0.0.1:8000"


st.set_page_config(
    page_title="AI 智能问答系统",
    page_icon="🤖",
    layout="wide"
)


# =========================================================
# Session State
# =========================================================

if "token" not in st.session_state:
    st.session_state.token = None

if "username" not in st.session_state:
    st.session_state.username = None

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "initialized" not in st.session_state:
    st.session_state.initialized = False


# =========================================================
# 工具函数
# =========================================================

def auth_headers():
    """
    返回 JWT 请求头
    """
    if not st.session_state.token:
        return {}

    return {
        "Authorization": f"Bearer {st.session_state.token}"
    }


def get_error_message(response):
    """
    从后端统一错误格式中提取提示信息
    """
    try:
        data = response.json()

        return (
            data.get("message")
            or data.get("detail")
            or "请求失败"
        )

    except ValueError:
        return "请求失败"


def logout():
    """
    清除当前登录状态
    """
    st.session_state.token = None
    st.session_state.username = None
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.initialized = False


def handle_unauthorized(response):
    """
    处理 Token 失效
    """
    if response.status_code == 401:
        logout()
        st.rerun()


# =========================================================
# 登录
# =========================================================

def login_user(username, password):

    response = requests.post(
        f"{BACKEND_URL}/login",
        json={
            "username": username,
            "password": password
        },
        timeout=30
    )

    return response


# =========================================================
# 注册
# =========================================================

def register_user(username, password):

    response = requests.post(
        f"{BACKEND_URL}/register",
        json={
            "username": username,
            "password": password
        },
        timeout=30
    )

    return response


# =========================================================
# 获取当前用户
# =========================================================

def get_current_user():

    response = requests.get(
        f"{BACKEND_URL}/me",
        headers=auth_headers(),
        timeout=30
    )

    handle_unauthorized(response)

    response.raise_for_status()

    return response.json()


# =========================================================
# 创建聊天
# =========================================================

def create_new_session():

    response = requests.post(
        f"{BACKEND_URL}/session",
        headers=auth_headers(),
        json={
            "title": "新聊天"
        },
        timeout=30
    )

    handle_unauthorized(response)

    response.raise_for_status()

    return response.json()["session_id"]


# =========================================================
# 获取聊天列表
# =========================================================

def get_sessions():

    response = requests.get(
        f"{BACKEND_URL}/sessions",
        headers=auth_headers(),
        timeout=30
    )

    handle_unauthorized(response)

    response.raise_for_status()

    return response.json()


# =========================================================
# 获取聊天消息
# =========================================================

def get_messages(session_id):

    response = requests.get(
        f"{BACKEND_URL}/sessions/{session_id}/messages",
        headers=auth_headers(),
        timeout=30
    )

    handle_unauthorized(response)

    response.raise_for_status()

    return response.json()


# =========================================================
# 删除聊天
# =========================================================

def delete_session(session_id):

    response = requests.delete(
        f"{BACKEND_URL}/sessions/{session_id}",
        headers=auth_headers(),
        timeout=30
    )

    handle_unauthorized(response)

    response.raise_for_status()


# =========================================================
# 获取知识库
# =========================================================

def get_documents():

    response = requests.get(
        f"{BACKEND_URL}/documents",
        headers=auth_headers(),
        timeout=30
    )

    handle_unauthorized(response)

    response.raise_for_status()

    return response.json()["documents"]


# =========================================================
# 删除知识库文件
# =========================================================

def delete_document(filename):

    encoded_filename = quote(
        filename,
        safe=""
    )

    response = requests.delete(
        f"{BACKEND_URL}/documents/{encoded_filename}",
        headers=auth_headers(),
        timeout=30
    )

    handle_unauthorized(response)

    response.raise_for_status()


# =========================================================
# 上传 PDF
# =========================================================

def upload_document(uploaded_file):

    response = requests.post(
        f"{BACKEND_URL}/upload",
        headers=auth_headers(),
        files={
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                "application/pdf"
            )
        },
        timeout=120
    )

    handle_unauthorized(response)

    response.raise_for_status()

    return response.json()


# =========================================================
# 加载聊天
# =========================================================

def load_session(session_id):

    old_messages = get_messages(
        session_id
    )

    st.session_state.session_id = session_id
    st.session_state.messages = []

    for message in old_messages:

        st.session_state.messages.append(
            {
                "role": "user",
                "content": message["user_message"]
            }
        )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": message["ai_message"]
            }
        )


# =========================================================
# 登录 / 注册页面
# =========================================================

if not st.session_state.token:

    st.title("🤖 AI 智能问答系统")

    st.caption(
        "企业级 AI 知识库问答系统"
    )

    tab_login, tab_register = st.tabs(
        [
            "🔐 登录",
            "📝 注册"
        ]
    )

    # =====================================================
    # 登录
    # =====================================================

    with tab_login:

        st.subheader("用户登录")

        with st.form(
            "login_form"
        ):

            username = st.text_input(
                "用户名",
                placeholder="请输入用户名"
            )

            password = st.text_input(
                "密码",
                type="password",
                placeholder="请输入密码"
            )

            submitted = st.form_submit_button(
                "登录",
                use_container_width=True
            )

        if submitted:

            if not username or not password:

                st.warning(
                    "请输入用户名和密码"
                )

            else:

                try:

                    response = login_user(
                        username.strip(),
                        password
                    )

                    if response.status_code == 200:

                        data = response.json()

                        st.session_state.token = (
                            data["access_token"]
                        )

                        st.session_state.username = (
                            data["username"]
                        )

                        st.session_state.session_id = None
                        st.session_state.messages = []
                        st.session_state.initialized = False

                        st.success(
                            "登录成功"
                        )

                        st.rerun()

                    else:

                        st.error(
                            get_error_message(
                                response
                            )
                        )

                except requests.exceptions.RequestException as e:

                    st.error(
                        f"无法连接后端：{e}"
                    )

    # =====================================================
    # 注册
    # =====================================================

    with tab_register:

        st.subheader("创建账号")

        with st.form(
            "register_form"
        ):

            new_username = st.text_input(
                "用户名",
                placeholder="3-50 个字符"
            )

            new_password = st.text_input(
                "密码",
                type="password",
                placeholder="至少 6 个字符"
            )

            register_submitted = st.form_submit_button(
                "注册",
                use_container_width=True
            )

        if register_submitted:

            if not new_username or not new_password:

                st.warning(
                    "请输入用户名和密码"
                )

            else:

                try:

                    response = register_user(
                        new_username.strip(),
                        new_password
                    )

                    if response.status_code == 200:

                        st.success(
                            "注册成功，请切换到登录页面登录"
                        )

                    else:

                        st.error(
                            get_error_message(
                                response
                            )
                        )

                except requests.exceptions.RequestException as e:

                    st.error(
                        f"无法连接后端：{e}"
                    )

    st.stop()


# =========================================================
# 已登录页面
# =========================================================

st.title("🤖 AI 智能问答系统")


# =========================================================
# 初始化当前用户
# =========================================================

try:

    if not st.session_state.initialized:

        user_data = get_current_user()

        st.session_state.username = (
            user_data["username"]
        )

        sessions = get_sessions()

        if sessions:

            # 默认打开最近的一条聊天
            st.session_state.session_id = (
                sessions[0]["id"]
            )

            load_session(
                st.session_state.session_id
            )

        else:

            # 没有聊天时，不主动创建空聊天
            st.session_state.session_id = None
            st.session_state.messages = []

        st.session_state.initialized = True


except requests.exceptions.HTTPError as e:

    if (
        e.response is not None
        and e.response.status_code == 401
    ):

        logout()
        st.rerun()

    else:

        st.error(
            f"加载系统失败：{e}"
        )

except requests.exceptions.RequestException as e:

    st.error(
        f"无法连接后端：{e}"
    )


# =========================================================
# 左侧边栏
# =========================================================

with st.sidebar:

    # =====================================================
    # 用户信息
    # =====================================================

    st.header("👤 用户")

    st.write(
        f"当前用户：**{st.session_state.username}**"
    )

    if st.button(
        "退出登录",
        use_container_width=True
    ):

        logout()
        st.rerun()

    st.divider()

    # =====================================================
    # 聊天记录
    # =====================================================

    st.header("💬 聊天记录")

    # 新聊天
    if st.button(
        "＋ 新聊天",
        use_container_width=True
    ):

        try:

            session_id = create_new_session()

            st.session_state.session_id = (
                session_id
            )

            st.session_state.messages = []

            st.rerun()

        except requests.exceptions.RequestException as e:

            st.error(
                f"创建聊天失败：{e}"
            )

    st.divider()

    # =====================================================
    # 历史聊天列表
    # =====================================================

    try:

        sessions = get_sessions()

        if not sessions:

            st.caption(
                "暂无聊天记录"
            )

        for session in sessions:

            session_id = session["id"]
            title = session["title"]

            col1, col2 = st.columns(
                [5, 1]
            )

            # -----------------------------
            # 打开聊天
            # -----------------------------

            with col1:

                if st.button(
                    title,
                    key=f"session_{session_id}",
                    use_container_width=True
                ):

                    try:

                        load_session(
                            session_id
                        )

                        st.rerun()

                    except requests.exceptions.RequestException as e:

                        st.error(
                            f"加载聊天失败：{e}"
                        )

            # -----------------------------
            # 删除聊天
            # -----------------------------

            with col2:

                if st.button(
                    "🗑️",
                    key=f"delete_{session_id}"
                ):

                    try:

                        delete_session(
                            session_id
                        )

                        if (
                            st.session_state.session_id
                            == session_id
                        ):

                            st.session_state.session_id = None
                            st.session_state.messages = []

                        st.rerun()

                    except requests.exceptions.RequestException as e:

                        st.error(
                            f"删除聊天失败：{e}"
                        )

    except requests.exceptions.RequestException as e:

        st.warning(
            "聊天记录暂时无法加载"
        )

    st.divider()

    # =====================================================
    # 知识库
    # =====================================================

    st.header("📚 知识库")

    uploaded_file = st.file_uploader(
        "上传 PDF 文档",
        type=["pdf"]
    )

    if uploaded_file is not None:

        st.caption(
            f"当前文件：{uploaded_file.name}"
        )

        if st.button(
            "上传到知识库",
            use_container_width=True
        ):

            try:

                with st.spinner(
                    "正在解析 PDF 并建立向量索引..."
                ):

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
                        f"Chunk 数量：{result['chunk_count']}"
                    )

                    st.rerun()

            except requests.exceptions.HTTPError as e:

                st.error(
                    f"上传失败：{get_error_message(e.response)}"
                )

            except requests.exceptions.RequestException as e:

                st.error(
                    f"上传失败：{e}"
                )

    # =====================================================
    # 知识库文件列表
    # =====================================================

    try:

        documents = get_documents()

        if not documents:

            st.caption(
                "当前知识库为空"
            )

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

                try:

                    delete_document(
                        filename
                    )

                    st.success(
                        "文档已删除"
                    )

                    st.rerun()

                except requests.exceptions.HTTPError as e:

                    st.error(
                        f"删除失败：{get_error_message(e.response)}"
                    )

                except requests.exceptions.RequestException as e:

                    st.error(
                        f"删除失败：{e}"
                    )

    except requests.exceptions.RequestException:

        st.warning(
            "知识库接口暂时不可用"
        )


# =========================================================
# 当前聊天
# =========================================================

if st.session_state.session_id is not None:

    st.caption(
        f"当前会话 ID：{st.session_state.session_id}"
    )


# =========================================================
# 显示历史消息
# =========================================================

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.write(
            message["content"]
        )


# =========================================================
# 用户输入
# =========================================================

question = st.chat_input(
    "请输入你的问题"
)


if question:

    # =====================================================
    # 没有聊天时，自动创建
    # =====================================================

    if st.session_state.session_id is None:

        try:

            st.session_state.session_id = (
                create_new_session()
            )

        except requests.exceptions.RequestException as e:

            st.error(
                f"创建聊天失败：{e}"
            )

            st.stop()

    # =====================================================
    # 显示用户问题
    # =====================================================

    with st.chat_message(
        "user"
    ):

        st.write(
            question
        )

    try:

        # =================================================
        # 请求后端
        # =================================================

        response = requests.post(
            f"{BACKEND_URL}/chat",

            headers=auth_headers(),

            json={
                "message": question,
                "session_id":
                    st.session_state.session_id
            },

            stream=True,

            timeout=120
        )

        # -------------------------------------------------
        # Token 过期
        # -------------------------------------------------

        if response.status_code == 401:

            logout()

            st.warning(
                "登录状态已失效，请重新登录。"
            )

            st.rerun()

        # -------------------------------------------------
        # 没有权限
        # -------------------------------------------------

        if response.status_code == 403:

            st.error(
                get_error_message(
                    response
                )
            )

            st.stop()

        response.raise_for_status()

        response.encoding = "utf-8"

        # =================================================
        # 流式数据生成器
        # =================================================

        def response_generator():

            for chunk in response.iter_content(
                chunk_size=None,
                decode_unicode=True
            ):

                if chunk:

                    yield chunk

        # =================================================
        # 显示 AI 回答
        # =================================================

        with st.chat_message(
            "assistant"
        ):

            full_response = st.write_stream(
                response_generator()
            )

        # =================================================
        # 保存前端状态
        # =================================================

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

    except requests.exceptions.HTTPError as e:

        st.error(
            f"请求失败：{get_error_message(e.response)}"
        )

    except requests.exceptions.RequestException as e:

        st.error(
            f"请求后端失败：{e}"
        )

