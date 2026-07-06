# WebSocket Server

基于FastAPI和Uvicorn的WebSocket服务器，支持实时通信、用户状态管理和消息广播。

## 功能特性

- WebSocket实时通信
- JWT认证
- 用户状态管理
- 多设备支持
- 消息广播
- MySQL数据库支持
- SQLAlchemy ORM

## 项目结构

```
server/
├── app/                     # 主应用目录
│   ├── models/              # 数据模型
│   ├── schemas/             # Pydantic模型
│   ├── api/                 # API路由
│   ├── core/                # 核心功能
│   ├── services/            # 业务逻辑
│   └── utils/               # 工具函数
├── tests/                   # 测试目录
├── alembic/                 # 数据库迁移
├── .env                     # 环境变量
└── requirements.txt         # 依赖
client/
├── app/                    # 主应用目录
│   ├── models/             # 数据模型
│   ├── websocket/          # websocket
│   ├── core/               # 核心功能
│   ├── tasks/              # 采集任务逻辑
│   └── utils/              # 工具函数
│   └── service/            # 业务逻辑
│   └── ui/                 # 图形界面
├── tests/                  # 测试目录
├── .env                    # 环境变量
└── requirements.txt        # 依赖
```

## 安装和运行

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置环境变量：
```bash
cp .env.example .env
# 编辑.env文件，设置数据库连接等信息
```

4. 运行服务器：
```bash
python -m app.main
```

## API文档

启动服务器后，访问以下地址查看API文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## WebSocket连接

WebSocket端点：`ws://localhost:8000/ws`

连接时需要提供JWT令牌：
```
ws://localhost:8000/ws?token=YOUR_JWT_TOKEN
```

## 消息格式

### 发送消息
```json
{
    "type": "message",
    "content": "Hello, world!"
}
```

### 加入房间
```json
{
    "type": "join_room",
    "room_id": "room1"
}
```

### 离开房间
```json
{
    "type": "leave_room",
    "room_id": "room1"
}
```

### 房间消息
```json
{
    "type": "room_message",
    "room_id": "room1",
    "content": "Hello room!"
}
```

## 开发

1. 创建新的数据库迁移：
```bash
alembic revision --autogenerate -m "description"
```

2. 运行测试：
```bash
pytest
```

## 贡献

欢迎提交Pull Request或Issue。

## 许可证

MIT 