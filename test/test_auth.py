from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token
)


def test_password_hash_and_verify():

    password = "12345678"

    password_hash = hash_password(
        password
    )

    # 哈希值不应该等于原密码
    assert password_hash != password

    # 正确密码应该验证成功
    assert verify_password(
        password,
        password_hash
    ) is True

    # 错误密码应该验证失败
    assert verify_password(
        "wrong_password",
        password_hash
    ) is False


def test_jwt_create_and_decode():

    token = create_access_token(
        user_id=123,
        username="testuser"
    )

    payload = decode_access_token(
        token
    )

    assert payload["user_id"] == 123
    assert payload["username"] == "testuser"