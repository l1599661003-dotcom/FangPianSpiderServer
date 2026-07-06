import hashlib
import time
import uuid
import base64
import os

# 签名工具类
from Crypto.Cipher import DES3
from Crypto.Util.Padding import pad

class SignUtil:

    # 获取签名参数
    @staticmethod
    def get_sign_params(params: dict) -> dict:
        params["app_id"] = os.getenv("APP_ID")
        params["timestamp"] = int(time.time())
        params["nonce"] = str(uuid.uuid4())
        return params

    # 生成clientId
    # 1. 读取环境变量中的密钥
    # 2. 用3DES加密方法，根据密钥生成clientId，生成的内容可逆向解析
    @staticmethod
    def generate_client_id(content: str) -> str:
        key = os.getenv("KEY", '1234567890abcdefghijklmn')
        cipher = DES3.new(key.encode('utf-8'), DES3.MODE_ECB)
        ciphertext = cipher.encrypt(pad(content.encode('utf-8'), DES3.block_size))
        return base64.b64encode(ciphertext).decode()

    # 解密clientId
    @staticmethod
    def decrypt_client_id(client_id: str) -> str:
        key = os.getenv("KEY", '1234567890abcdefghijklmn')
        cipher = DES3.new(key.encode('utf-8'), DES3.MODE_ECB)
        plaintext = cipher.decrypt(base64.b64decode(client_id))
        return plaintext.decode()
    
    # 生成clientSecret
    # 1. 用3DES加密方法，通过clientId为密钥，生成clientSecret
    @staticmethod
    def generate_client_secret(client_id: str) -> str:
        key = SignUtil.decrypt_client_id(client_id)
        # 截取key的前8位
        key = key[:16]
        cipher = DES3.new(key.encode('utf-8'), DES3.MODE_ECB)
        ciphertext = cipher.encrypt(pad(client_id.encode('utf-8'), DES3.block_size))
        return base64.b64encode(ciphertext).decode()

    # 获取签名
    @staticmethod
    def get_sign(params: dict) -> str:
        sign_str = ""
        client_secret = SignUtil.generate_client_secret(params["clientId"])

        for key, value in params.items():
            if key == "sign":
                continue
            sign_str += f"{key}={value}&"
        sign_str += f"clientSecret={client_secret}"
        return hashlib.md5(sign_str.encode()).hexdigest() 

    # 验证签名
    @staticmethod
    def verify_sign(params: dict) -> bool:
        sign = params["sign"]
        params.pop("sign")
        return sign == SignUtil.get_sign(params)

    @staticmethod
    def verify_client_id(params) -> str:
        # client_id = SignUtil.decrypt_client_id(params["clientId"])
        return " "

if __name__ == "__main__":
    params = {
        "clientId": "4UQUZJwwrY+BJCkiGDgUPA==",
        "timestamp": 1716230400,
        "nonce": "1234567890"
    }
    client_id = SignUtil.generate_client_id("牛哥密钥")
    print(client_id)
    print(SignUtil.generate_client_secret(client_id))

    print(SignUtil.get_sign(params))
    params["sign"] = SignUtil.get_sign(params)
    print(SignUtil.verify_sign(params))