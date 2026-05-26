#!/usr/bin/env python3
"""
密钥生成器 - 管理员工具
========================
功能：
  1. 生成 RSA-2048 密钥对（首次运行）
  2. 查询设备硬件ID
  3. 为指定硬件ID生成许可证
  4. 生成管理员代码（已内置，无需生成）

使用：
  python tools/keygen.py                  # 交互模式
  python tools/keygen.py --hwid           # 显示本机硬件ID
  python tools/keygen.py --genkey         # 生成RSA密钥对
  python tools/keygen.py --issue <hwid> [--expiry 2026-12-31]  # 签发许可证
"""

import argparse
import base64
import hashlib
import json
import os
import platform
import sys
import uuid
from datetime import datetime, timedelta

KEYS_DIR = os.path.join(os.path.dirname(__file__), "..", "keys")
PRIVATE_KEY_FILE = os.path.join(KEYS_DIR, "private.pem")
PUBLIC_KEY_FILE = os.path.join(KEYS_DIR, "public.pem")

ADMIN_CODE = "SEAICE-ADMIN-2025"


def get_hardware_id(node: str = None, mac: int = None) -> str:
    if mac is None:
        mac = uuid.getnode()
    if node is None:
        node = platform.node()
    raw = f"{mac}:{node}:{platform.system()}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def generate_keypair():
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    os.makedirs(KEYS_DIR, exist_ok=True)
    print("生成 RSA-2048 密钥对...")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with open(PRIVATE_KEY_FILE, "wb") as f:
        f.write(private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))

    pub_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with open(PUBLIC_KEY_FILE, "wb") as f:
        f.write(pub_pem)

    print(f"私钥: {PRIVATE_KEY_FILE}")
    print(f"公钥: {PUBLIC_KEY_FILE}")
    print()
    print("请将以下公钥替换到 core/license.py 的 _PUBLIC_KEY_PEM 变量：")
    print("-" * 60)
    print(pub_pem.decode())
    print("-" * 60)


def load_private_key():
    from cryptography.hazmat.primitives import serialization
    if not os.path.exists(PRIVATE_KEY_FILE):
        print("错误: 未找到私钥，请先运行 --genkey")
        sys.exit(1)
    with open(PRIVATE_KEY_FILE, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def issue_license(hw_id: str, expiry: str = None, note: str = "") -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    private_key = load_private_key()

    payload = {
        "type": "hardware",
        "hardware_id": hw_id,
        "issued": datetime.now().strftime("%Y-%m-%d"),
        "note": note,
    }
    if expiry:
        payload["expiry"] = expiry

    payload_bytes = json.dumps(payload, sort_keys=True).encode()
    sig = private_key.sign(payload_bytes, padding.PKCS1v15(), hashes.SHA256())
    payload["signature"] = base64.b64encode(sig).decode()

    license_str = base64.b64encode(json.dumps(payload).encode()).decode()
    return license_str


def interactive_mode():
    print("=" * 55)
    print("  极地海冰平台 - 密钥与许可证管理工具")
    print("=" * 55)
    print()

    while True:
        print("选择操作：")
        print("  1. 生成 RSA 密钥对（首次部署运行一次）")
        print("  2. 查看本机硬件 ID")
        print("  3. 为硬件 ID 签发许可证")
        print("  4. 查看管理员代码")
        print("  0. 退出")
        choice = input("\n请输入选项: ").strip()

        if choice == "1":
            generate_keypair()

        elif choice == "2":
            hw = get_hardware_id()
            print(f"\n本机硬件 ID: {hw}\n")

        elif choice == "3":
            hw = input("输入目标设备硬件 ID: ").strip()
            if not hw:
                print("硬件 ID 不能为空")
                continue
            exp = input("有效期至（YYYY-MM-DD，留空永久有效）: ").strip()
            note = input("备注（选填）: ").strip()
            try:
                lic = issue_license(hw, expiry=exp or None, note=note)
                print("\n许可证（Base64）：")
                print("-" * 55)
                print(lic)
                print("-" * 55)
                out = f"license_{hw[:8]}.txt"
                with open(out, "w") as f:
                    f.write(lic)
                print(f"已保存至: {out}\n")
            except Exception as e:
                print(f"签发失败: {e}")

        elif choice == "4":
            print(f"\n管理员代码: {ADMIN_CODE}")
            print("（此代码已内置于软件，无需生成，分发给受信任管理员即可）\n")

        elif choice == "0":
            break
        else:
            print("无效选项")

        print()


def main():
    parser = argparse.ArgumentParser(description="极地海冰平台密钥生成器")
    parser.add_argument("--hwid", action="store_true", help="显示本机硬件ID")
    parser.add_argument("--genkey", action="store_true", help="生成RSA密钥对")
    parser.add_argument("--issue", metavar="HWID", help="为指定硬件ID签发许可证")
    parser.add_argument("--expiry", metavar="YYYY-MM-DD", help="许可证有效期")
    parser.add_argument("--note", default="", help="备注信息")
    args = parser.parse_args()

    if args.hwid:
        print(get_hardware_id())
    elif args.genkey:
        generate_keypair()
    elif args.issue:
        lic = issue_license(args.issue, expiry=args.expiry, note=args.note)
        print(lic)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
