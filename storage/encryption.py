"""
API Key加密工具
使用Fernet + PBKDF2HMAC实现per-user密钥派生和加密
仅通过环境变量 MASTER_ENCRYPTION_KEY 获取主密钥
"""

import os
import base64
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet, InvalidToken

# 默认用户ID（单用户阶段）
DEFAULT_USER_ID = "default"

# PBKDF2参数
PBKDF2_ITERATIONS = 600_000  # OWASP推荐值


def _get_master_key() -> bytes:
    """从环境变量获取主加密密钥（必须配置）"""
    key = os.getenv("MASTER_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "MASTER_ENCRYPTION_KEY 环境变量未设置。"
            "请运行: python3 -c \"from storage.encryption import generate_master_key; generate_master_key()\""
        )
    return key.encode() if isinstance(key, str) else key


def _derive_key(master_key: bytes, user_id: str) -> bytes:
    """
    从主密钥+用户ID派生用户级Fernet密钥

    使用PBKDF2HMAC-SHA256，以user_id作为salt
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=user_id.encode("utf-8"),
        iterations=PBKDF2_ITERATIONS,
    )
    derived = kdf.derive(master_key)
    # Fernet需要URL-safe base64编码的32字节密钥
    return base64.urlsafe_b64encode(derived)


def encrypt_api_key(api_key: str, user_id: str = DEFAULT_USER_ID) -> str:
    """
    加密API Key

    Args:
        api_key: 明文API Key
        user_id: 用户ID（默认"default"）

    Returns:
        加密后的字符串
    """
    master_key = _get_master_key()
    fernet_key = _derive_key(master_key, user_id)
    fernet = Fernet(fernet_key)
    encrypted = fernet.encrypt(api_key.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_api_key(encrypted: str, user_id: str = DEFAULT_USER_ID) -> str:
    """
    解密API Key

    Args:
        encrypted: 加密的API Key字符串
        user_id: 用户ID（默认"default"）

    Returns:
        明文API Key

    Raises:
        ValueError: 解密失败（密钥不匹配或数据损坏）
    """
    master_key = _get_master_key()
    fernet_key = _derive_key(master_key, user_id)
    fernet = Fernet(fernet_key)

    try:
        decrypted = fernet.decrypt(encrypted.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken:
        raise ValueError("API Key解密失败：密钥不匹配或数据已损坏")


def generate_master_key() -> str:
    """
    生成新的主加密密钥并打印

    将输出添加到环境变量或.env文件中：
    MASTER_ENCRYPTION_KEY=<生成的密钥>
    """
    key = Fernet.generate_key().decode("utf-8")
    print(f"生成的 MASTER_ENCRYPTION_KEY:\n{key}")
    print("\n请将此密钥添加到环境变量或.env文件中。")
    return key
