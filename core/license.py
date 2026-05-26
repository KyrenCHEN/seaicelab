import base64
import hashlib
import json
import os
import platform
import uuid
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# 部署前替换为 tools/keygen.py 生成的公钥
_PUBLIC_KEY_PEM = b"""\
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2a2rwplBQLzHPZe5TNJF
HgCkBuFJcUTNMQMRsVfqMXbV8QJe5eMzPGnbGfEYanMEqJtmJ3LzorOkwKbLuEM
dMfXH5eXhQPL0Br7GHJeP5F4vJTnNxPLMPeEz6vbmkKz5HmqJjGNrK/vOQ+YHFM
9e9tY01Q2b1R0X7bKHfVTHW7E9wMnJT4NMv4TcP8WP8tHqZMhMz7tNJpUblMf2y
rI3KGr5X8y2QhgSCn+gv6tPFl9B6XQrEQT5g3eHqFrdWYnl5Pv8oVmWHjqyCLf
lP8qBFPLqOQjFKbdyxG8qJ0jV7mKlTiP7kCf8KgNbhP5Iy6nX2n5YTqGvEIQvQ
IDAQAB
-----END PUBLIC KEY-----
"""

ADMIN_MASTER_CODE = "SEAICE-ADMIN-2025"


def get_hardware_id() -> str:
    mac = uuid.getnode()
    node = platform.node()
    raw = f"{mac}:{node}:{platform.system()}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


class LicenseManager:
    LICENSE_FILE = os.path.join(os.path.expanduser("~"), ".seaice_platform", "license.lic")

    def __init__(self):
        self._valid = False
        self._info: dict = {}

    def check(self) -> tuple[bool, str]:
        if not os.path.exists(self.LICENSE_FILE):
            return False, "未找到许可证文件"
        try:
            with open(self.LICENSE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return False, "许可证文件损坏"

        if data.get("type") == "admin":
            if data.get("code") == ADMIN_MASTER_CODE:
                self._valid = True
                self._info = data
                return True, "管理员授权"
            return False, "管理员代码无效"

        hw_id = get_hardware_id()
        if data.get("hardware_id") != hw_id:
            return False, f"硬件ID不匹配（当前: {hw_id}）"

        expiry = data.get("expiry", "")
        if expiry and datetime.strptime(expiry, "%Y-%m-%d") < datetime.now():
            return False, f"许可证已于 {expiry} 过期"

        try:
            sig = base64.b64decode(data["signature"])
            payload = json.dumps(
                {k: v for k, v in data.items() if k != "signature"}, sort_keys=True
            ).encode()
            pub = serialization.load_pem_public_key(_PUBLIC_KEY_PEM)
            pub.verify(sig, payload, padding.PKCS1v15(), hashes.SHA256())
        except InvalidSignature:
            return False, "许可证签名无效"
        except Exception as e:
            return False, f"许可证验证失败: {e}"

        self._valid = True
        self._info = data
        return True, "许可证有效"

    def is_valid(self) -> bool:
        if not self._valid:
            ok, _ = self.check()
            return ok
        return True

    def activate_admin(self, code: str) -> tuple[bool, str]:
        if code != ADMIN_MASTER_CODE:
            return False, "管理员代码无效"
        os.makedirs(os.path.dirname(self.LICENSE_FILE), exist_ok=True)
        with open(self.LICENSE_FILE, "w", encoding="utf-8") as f:
            json.dump({"type": "admin", "code": code}, f)
        self._valid = True
        return True, "管理员授权成功"

    def activate_license(self, license_b64: str) -> tuple[bool, str]:
        try:
            data = json.loads(base64.b64decode(license_b64.strip()).decode())
        except Exception:
            return False, "许可证格式无效"
        os.makedirs(os.path.dirname(self.LICENSE_FILE), exist_ok=True)
        with open(self.LICENSE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return self.check()

    def get_hardware_id(self) -> str:
        return get_hardware_id()

    def get_info(self) -> dict:
        return self._info
