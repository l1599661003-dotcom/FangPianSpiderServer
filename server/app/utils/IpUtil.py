from fastapi import Request


# 获取客户端的 IP 地址
def get_ip_address(request: Request):
    forwarded_for = request.headers.get("X-Forwarded-For")

    if forwarded_for:
        # 如果有多个 IP 地址（可能有多个代理），返回第一个 IP 地址
        client_ip = forwarded_for.split(",")[0]
    else:
        # 如果没有 X-Forwarded-For 头部，使用 request.client 获取
        client_ip = request.client.host

    return client_ip
