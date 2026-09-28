from fastapi.testclient import TestClient

import app.main as main


def create_test_client(user_id=1, username="testuser"):

    main.app.dependency_overrides[
        main.get_current_user
    ] = lambda: {
        "user_id": user_id,
        "username": username
    }

    return TestClient(main.app)


def close_test_client():

    main.app.dependency_overrides.clear()


# =========================
# 登录测试
# =========================

def test_login_success(monkeypatch):

    client = create_test_client()

    monkeypatch.setattr(
        main,
        "get_user_by_username",
        lambda username: (
            1,
            "testuser",
            "fake_password_hash"
        )
    )

    monkeypatch.setattr(
        main,
        "verify_password",
        lambda password, password_hash: True
    )

    monkeypatch.setattr(
        main,
        "create_access_token",
        lambda user_id, username: "test-token"
    )

    response = client.post(
        "/login",
        json={
            "username": "testuser",
            "password": "12345678"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == 1
    assert data["username"] == "testuser"
    assert data["access_token"] == "test-token"

    close_test_client()


# =========================
# 注册测试
# =========================

def test_register_success(monkeypatch):

    client = create_test_client()

    monkeypatch.setattr(
        main,
        "get_user_by_username",
        lambda username: None
    )

    monkeypatch.setattr(
        main,
        "hash_password",
        lambda password: "fake_hash"
    )

    monkeypatch.setattr(
        main,
        "create_user",
        lambda username, password_hash: 2
    )

    response = client.post(
        "/register",
        json={
            "username": "newuser",
            "password": "12345678"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == 2
    assert data["username"] == "newuser"

    close_test_client()


# =========================
# 未认证测试
# =========================

def test_me_without_token():

    # 不设置 dependency override
    main.app.dependency_overrides.clear()

    client = TestClient(
        main.app
    )

    response = client.get(
        "/me"
    )

    assert response.status_code == 401

    data = response.json()

    assert data["code"] == 401

    main.app.dependency_overrides.clear()


# =========================
# 422 参数错误
# =========================

def test_login_validation_error():

    main.app.dependency_overrides.clear()

    client = TestClient(
        main.app
    )

    response = client.post(
        "/login",
        json={
            "username": "testuser"
        }
    )

    assert response.status_code == 422

    data = response.json()

    assert data["code"] == 422
    assert data["message"] == "请求参数错误"

    main.app.dependency_overrides.clear()


# =========================
# 聊天列表用户隔离
# =========================

def test_sessions_are_user_scoped(
    monkeypatch
):

    client = create_test_client(
        user_id=2,
        username="testuser2"
    )

    called_user_ids = []

    def fake_get_sessions(user_id):

        called_user_ids.append(
            user_id
        )

        return [
            (
                100,
                "用户2自己的聊天"
            )
        ]

    monkeypatch.setattr(
        main,
        "get_sessions",
        fake_get_sessions
    )

    response = client.get(
        "/sessions"
    )

    assert response.status_code == 200

    assert called_user_ids == [2]

    assert response.json() == [
        {
            "id": 100,
            "title": "用户2自己的聊天"
        }
    ]

    close_test_client()


# =========================
# 消息越权测试
# =========================

def test_messages_forbidden_for_other_user(
    monkeypatch
):

    client = create_test_client(
        user_id=2,
        username="testuser2"
    )

    monkeypatch.setattr(
        main,
        "check_session_owner",
        lambda session_id, user_id: False
    )

    response = client.get(
        "/sessions/44/messages"
    )

    assert response.status_code == 403

    data = response.json()

    assert data["code"] == 403
    assert data["message"] == "无权访问该聊天会话"

    close_test_client()


# =========================
# 聊天越权测试
# =========================

def test_chat_forbidden_for_other_user(
    monkeypatch
):

    client = create_test_client(
        user_id=2,
        username="testuser2"
    )

    monkeypatch.setattr(
        main,
        "check_session_owner",
        lambda session_id, user_id: False
    )

    response = client.post(
        "/chat",
        json={
            "message": "测试越权",
            "session_id": 44
        }
    )

    assert response.status_code == 403

    data = response.json()

    assert data["code"] == 403
    assert data["message"] == "无权访问该聊天会话"

    close_test_client()


# =========================
# 知识库用户隔离
# =========================

def test_documents_are_user_scoped(
    monkeypatch
):

    client = create_test_client(
        user_id=2,
        username="testuser2"
    )

    called_user_ids = []

    def fake_get_documents(user_id):

        called_user_ids.append(
            user_id
        )

        return [
            (
                "testuser2.pdf",
                5
            )
        ]

    monkeypatch.setattr(
        main,
        "get_documents",
        fake_get_documents
    )

    response = client.get(
        "/documents"
    )

    assert response.status_code == 200

    assert called_user_ids == [2]

    assert response.json() == {
        "documents": [
            [
                "testuser2.pdf",
                5
            ]
        ]
    }

    close_test_client()


# =========================
# 知识库删除越权测试
# =========================

def test_document_delete_forbidden(
    monkeypatch
):

    client = create_test_client(
        user_id=2,
        username="testuser2"
    )

    monkeypatch.setattr(
        main,
        "check_document_exists",
        lambda filename, user_id: False
    )

    response = client.delete(
        "/documents/testuser.pdf"
    )

    assert response.status_code == 404

    data = response.json()

    assert data["code"] == 404
    assert data["message"] == "文件不存在"

    close_test_client()