import json
import os

import certifi
import requests
# 获取飞书token
from loguru import logger


def get_feishu_token():
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        logger.error("FEISHU_APP_ID or FEISHU_APP_SECRET is not configured")
        return None

    url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
    headers = {
        'Content-Type': 'application/json; charset=utf-8'
    }
    data = {
        'app_id': app_id,
        'app_secret': app_secret
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        return response_data.get('app_access_token', '')
    except requests.RequestException as e:
        print(f"获取飞书Token失败: {e}")
        return None


# 获取飞书请求头
def get_feishu_headers():
    return {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {get_feishu_token()}'
    }


# 查询飞书表格信息
def read_table_content(app, table, view):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app}/tables/{table}/records/search?page_size=500"
    headers = get_feishu_headers()
    try:
        response = requests.post(url, headers=headers, data=json.dumps({'view_id': view}), verify=False, timeout=30)
        response.raise_for_status()
        response_data = response.json()

        if response_data.get('code') != 0:
            print(f"飞书API返回错误: {response_data}")
            return None

        # 获取总记录数和第一页数据
        total = response_data.get("data", {}).get("total", 0)
        items = response_data.get("data", {}).get("items", [])
        page_token = response_data.get("data", {}).get("page_token", "")

        # 如果总记录数大于 500，继续分页查询
        if total > 500:
            page = (total + 499) // 500  # 计算总页数
            for i in range(1, page):
                paginated_url = f"{url}&page_token={page_token}"
                paginated_response = requests.post(paginated_url, headers=headers, data=json.dumps({'view_id': view}),
                                                   verify=False)
                paginated_data = paginated_response.json()

                items.extend(paginated_data.get("data", {}).get("items", []))
                page_token = paginated_data.get("data", {}).get("page_token", "")

                if not page_token:
                    break
        return items
    except requests.RequestException as e:
        print(f"查询飞书表格信息失败：{e}")
        return None


# 查询飞书单条信息
def search_feishu_record(app_token, table_id, view_id, filters):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search?page_size=500"
    headers = get_feishu_headers()
    data = {
        "view_id": view_id,
        "filter": filters
    }

    try:
        # 第一次查询
        response = requests.post(url, headers=headers, json=data, verify=False)
        response_data = response.json()

        # 获取总记录数和第一页数据
        total = response_data.get("data", {}).get("total", 0)
        items = response_data.get("data", {}).get("items", [])
        page_token = response_data.get("data", {}).get("page_token", "")

        # 如果总记录数大于 500，继续分页查询
        if total > 500:
            page = (total + 499) // 500  # 计算总页数
            for i in range(1, page):
                # 添加 page_token 参数
                paginated_url = f"{url}&page_token={page_token}"
                paginated_response = requests.post(paginated_url, headers=headers, json=data, verify=False)
                paginated_data = paginated_response.json()

                # 合并当前页数据
                items.extend(paginated_data.get("data", {}).get("items", []))
                page_token = paginated_data.get("data", {}).get("page_token", "")

                # 如果没有下一页，退出循环
                if not page_token:
                    break

        return items

    except requests.RequestException as e:
        print(f"查询飞书单条信息失败: {e}")
        return None


# 发邀约打标签查询筛选条件
def search_feishu_record2(app_token, table_id, view_id, field_name, field_value):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search?page_size=500"
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {get_feishu_token()}'
    }
    data = {
        "view_id": view_id,
        "sort": [
            {
                "field_name": '月总营收',
                "desc": "true",
            }
        ],
        "filter": {
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": field_name,
                    "operator": "is",
                    "value": [field_value]
                },
                {
                    "field_name": '是否进群',
                    "operator": "isEmpty",
                    "value": []
                },
                {
                    "field_name": '区分列',
                    "operator": "isEmpty",
                    "value": []
                },
                {
                    "field_name": '发送邀约产品',
                    "operator": "isEmpty",
                    "value": []
                },
                {
                    "field_name": '是否发送邀约',
                    "operator": "isEmpty",
                    "value": []
                },
                {
                    "field_name": '微信号',
                    "operator": "isEmpty",
                    "value": []
                },
                {
                    "field_name": '微信号 副本',
                    "operator": "isEmpty",
                    "value": []
                },
                {
                    "field_name": '添加微信核对人',
                    "operator": "isEmpty",
                    "value": []
                }, {
                    "field_name": '进群核对人',
                    "operator": "isEmpty",
                    "value": []
                }, {
                    "field_name": '金虎VX',
                    "operator": "isEmpty",
                    "value": []
                }, {
                    "field_name": '是否添加成功计数',
                    "operator": "is",
                    "value": [0]
                }, {
                    "field_name": '返点登记',
                    "operator": "isEmpty",
                    "value": []
                }, {
                    "field_name": '返点备注',
                    "operator": "isEmpty",
                    "value": []
                }, {
                    "field_name": '合作返点（二核后',
                    "operator": "isEmpty",
                    "value": []
                }, {
                    "field_name": '是否签约博主',
                    "operator": "isNot",
                    "value": ['是']
                }, {
                    "field_name": '阅读量来源的【发现页】占比',
                    "operator": "isGreaterEqual",
                    "value": [0.55]
                },
                {
                    "field_name": '曝光量来源的【发现页】占比',
                    "operator": "isGreaterEqual",
                    "value": [0.55]
                }, {
                    "field_name": '备注',
                    "operator": "isEmpty",
                    "value": []
                }, {
                    "field_name": '区分列-流量组用',
                    "operator": "isEmpty",
                    "value": []
                }
            ]
        }
    }

    try:
        # 第一次查询
        response = requests.post(url, headers=headers, json=data, verify=False)
        response_data = response.json()

        # 获取总记录数和第一页数据
        total = response_data.get("data", {}).get("total", 0)
        items = response_data.get("data", {}).get("items", [])
        page_token = response_data.get("data", {}).get("page_token", "")

        # 如果总记录数大于 500，继续分页查询
        if total > 500:
            page = (total + 499) // 500  # 计算总页数
            for i in range(1, page):
                # 添加 page_token 参数
                paginated_url = f"{url}&page_token={page_token}"
                paginated_response = requests.post(paginated_url, headers=headers, json=data, verify=False)
                paginated_data = paginated_response.json()

                # 合并当前页数据
                items.extend(paginated_data.get("data", {}).get("items", []))
                page_token = paginated_data.get("data", {}).get("page_token", "")

                # 如果没有下一页，退出循环
                if not page_token:
                    break

        return items

    except requests.RequestException as e:
        print(f"查询飞书单条信息失败：{e}")
        return None


# 打水号查询筛选条件
def search_feishu_record3(app_token, table_id, view_id):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search?page_size=500"
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {get_feishu_token()}'
    }
    data = {
        "view_id": view_id,
        "filter": {
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": '阅读量来源的【发现页】占比',
                    "operator": "isGreaterEqual",
                    "value": [0.55]
                },
                {
                    "field_name": '曝光量来源的【发现页】占比',
                    "operator": "isGreaterEqual",
                    "value": [0.55]
                },
                {
                    "field_name": '内容类目1',
                    "operator": "contains",
                    "value": ["母婴"]
                },
                {
                    "field_name": '内容类目1',
                    "operator": "contains",
                    "value": ["家居家装"]
                },
                {
                    "field_name": '内容类目1',
                    "operator": "contains",
                    "value": ["科技数码"]
                }
            ]
        }
    }

    try:
        # 第一次查询
        response = requests.post(url, headers=headers, json=data, verify=False)
        response_data = response.json()

        # 获取总记录数和第一页数据
        total = response_data.get("data", {}).get("total", 0)
        items = response_data.get("data", {}).get("items", [])
        page_token = response_data.get("data", {}).get("page_token", "")

        # 如果总记录数大于 500，继续分页查询
        if total > 500:
            page = (total + 499) // 500  # 计算总页数
            for i in range(1, page):
                # 添加 page_token 参数
                paginated_url = f"{url}&page_token={page_token}"
                paginated_response = requests.post(paginated_url, headers=headers, json=data, verify=False)
                paginated_data = paginated_response.json()

                # 合并当前页数据
                items.extend(paginated_data.get("data", {}).get("items", []))
                page_token = paginated_data.get("data", {}).get("page_token", "")

                # 如果没有下一页，退出循环
                if not page_token:
                    break

        return items

    except requests.RequestException as e:
        print(f"查询飞书单条信息失败：{e}")
        return None


# 打重复号查询筛选条件
def search_feishu_record4(app_token, table_id, view_id, tiaojian):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search?page_size=500"
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {get_feishu_token()}'
    }
    data = {
        "view_id": view_id,
        "filter": {
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": '微信号',
                    "operator": "isNotEmpty",
                    "value": []
                }, {
                    "field_name": '微信号重复计数',
                    "operator": "isGreater",
                    "value": [1]
                }, {
                    "field_name": '金虎VX',
                    "operator": tiaojian,
                    "value": []
                },
            ]
        }
    }

    try:
        # 第一次查询
        response = requests.post(url, headers=headers, json=data, verify=False)
        response_data = response.json()

        # 获取总记录数和第一页数据
        total = response_data.get("data", {}).get("total", 0)
        items = response_data.get("data", {}).get("items", [])
        page_token = response_data.get("data", {}).get("page_token", "")

        # 如果总记录数大于 500，继续分页查询
        if total > 500:
            page = (total + 499) // 500  # 计算总页数
            for i in range(1, page):
                # 添加 page_token 参数
                paginated_url = f"{url}&page_token={page_token}"
                paginated_response = requests.post(paginated_url, headers=headers, json=data, verify=False)
                paginated_data = paginated_response.json()

                # 合并当前页数据
                items.extend(paginated_data.get("data", {}).get("items", []))
                page_token = paginated_data.get("data", {}).get("page_token", "")

                # 如果没有下一页，退出循环
                if not page_token:
                    break

        return items

    except requests.RequestException as e:
        print(f"查询飞书单条信息失败：{e}")
        return None


# 再飞书表格修改
def update_record(app_token, table_id, record_id, fields):
    headers = get_feishu_headers()
    body = {
        'fields': fields
    }
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
    try:
        response = requests.put(url, headers=headers, json=body, verify=certifi.where(), timeout=30)
        response_data = response.json()
        if response_data.get('msg') == 'success':
            print(f'飞书表格修改成功: {fields}')
        else:
            print(response_data)
    except requests.RequestException as e:
        print(f"更新飞书修改失败: {e}")


# 飞书发送消息
def feishu_send_message(message, key='5929796a-713a-4a67-bab9-15a2c7ebc8d7'):
    """飞书发送信息"""
    url = f'https://open.feishu.cn/open-apis/bot/v2/hook/{key}'
    data = {
        'msg_type': 'text',
        'content': {
            'text': message
        }
    }
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
    except Exception as e:
        print(f"飞书消息发送失败: {e}")


# 更新飞书token过期表格
def update_token_info(fields):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/PJISbPC5OaihG8sCfMpc4Wohnyb/tables/tblytxdwmyqhJt7D/records"
    headers = get_feishu_headers()
    body = {
        'fields': fields
    }
    try:
        response = requests.post(url, headers=headers, json=body, verify=False)
        response_data = response.json()
        if response_data.get('msg') == 'success':
            return f'飞书表格修改成功: {fields}'
            # print(f'飞书token过期表新增成功: {body}')
            # message = f"账号简称为:{fields['账号简称']},账号id为:{fields['账号id']},得token已经过期，请及时更换，链接为：https://gxumrig3imz.feishu.cn/base/PJISbPC5OaihG8sCfMpc4Wohnyb?table=tblDO9VqC6EMHGiY&view=vewJK6XVP4"
            # feishu_send_message(message)
    except requests.RequestException as e:
        print(f"飞书token过期表新增失败: {e}")


# 新增单条飞书记录
def insert_record(app_token, table_id, fields):
    response = requests.post(
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
        headers={
            'Content-Type': 'application/json; charset=utf-8',
            'Authorization': f'Bearer {get_feishu_token()}'
        },
        data=json.dumps({'fields': fields}),
        verify=certifi.where()
    )
    print(f"飞书表格新增成功{response.json()}")


# 批量新增飞书记录
def insert_records(app_token, table_id, inserts):
    chunk_size = 1000
    # 批量插入飞书记录
    if inserts:
        insert_chunks = [inserts[i:i + chunk_size] for i in range(0, len(inserts), chunk_size)]
        for chunk in insert_chunks:
            response = requests.post(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                headers={
                    'Content-Type': 'application/json; charset=utf-8',
                    'Authorization': f'Bearer {get_feishu_token()}'
                },
                data=json.dumps({'records': chunk}),
                verify=certifi.where()
            )
            logger.info(f"飞书表格新增成功{response.json()}")


# 批量新增飞书记录
def delete_records(app_token, table_id, records):
    chunk_size = 1000
    # 批量插入飞书记录
    if records:
        response = requests.post(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_delete",
            headers={
                'Content-Type': 'application/json; charset=utf-8',
                'Authorization': f'Bearer {get_feishu_token()}'
            },
            data=json.dumps({'records': records}),
            verify=certifi.where()
        )
        logger.info(f"飞书表格批量删除成功{response.json()}")


# 发送加急消息
def send_message(message):
    receive_id = "ou_76bb47b72c5dd6efe1b9d1729e111c16"
    receive_id_type = {"receive_id_type": "open_id"}
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {get_feishu_token()}'
    }
    payload = {
        "receive_id": receive_id,
        "msg_type": "text",
        "content": json.dumps({
            "text": message,
        }),
    }
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    try:
        response = requests.post(url, headers=headers, params=receive_id_type, json=payload, verify=certifi.where(),
                                 timeout=30)
        response_data = response.json()
        print(response_data)
        response.raise_for_status()
        if response_data.get('code') != 0:
            return f"发送消息失败：{response_data.get('msg')}"
            # send_phone(receive_id, response_data.get('data', {}).get('message_id'))
            # return
    except requests.RequestException as e:
        return f"发送消息失败：{e}"


# 发送加急电话
def send_phone(receive_id, message_id):
    receive_id = [receive_id]
    user_id_type = {"user_id_type": "open_id"}
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {get_feishu_token()}'
    }
    payload = {
        "user_id_list": receive_id,
    }
    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/urgent_phone"
    try:
        response = requests.patch(url, headers=headers, params=user_id_type, json=payload, verify=certifi.where(),
                                  timeout=30)
        response_data = response.json()
        print(response_data)
        response.raise_for_status()
    except requests.RequestException as e:
        return f"发送消息失败：{e}"
