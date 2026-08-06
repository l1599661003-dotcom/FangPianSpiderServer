import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, Depends
from loguru import logger
from starlette.websockets import WebSocketState

from server.app.core.WebSocketManager import WebSocketManager
from server.app.core.command_generator import CommandGenerator
from server.app.core.command_handler import handle_client_command
from server.app.utils.SessionUtil import get_token_from_websocket, get_current_user, get_cli_client_id

# 移除直接导入
# from server.app.main import ws_manager, task_scheduler

router = APIRouter()
# 不再创建新实例，而是使用全局单例
# manager = WebSocketManager()
command_generator = CommandGenerator()

# 依赖注入函数
def get_websocket_manager():
    from server.app.runtime import ws_manager
    return ws_manager

def get_task_scheduler():
    from server.app.runtime import task_scheduler
    return task_scheduler


# WebSocket端点
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, 
    token: str = Depends(get_token_from_websocket),
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
    scheduler = Depends(get_task_scheduler),
    cli_client_id = Depends(get_cli_client_id)
):
    client_id = None
    try:
        if cli_client_id:
            client_id = cli_client_id
        else:
        # 验证用户并获取客户端ID
            user = get_current_user(token)
            client_id = user.get('client_id')
        logger.info(f"客户端 {client_id} 尝试连接")

        # 连接WebSocket
        await ws_manager.connect(websocket, client_id)

        # 发送欢迎消息
        welcome_message = command_generator.generate_message(
            cmd="system_message",
            data={"message": "欢迎连接到爬虫服务器"},
            client_id=client_id
        )
        await ws_manager.send_message(client_id, welcome_message)

        # 检查该客户端是否有正在执行中的任务并恢复
        await scheduler.resume_client_tasks(client_id)

        try:
            while True:
                try:
                    # 检查连接状态
                    if websocket.client_state == WebSocketState.DISCONNECTED:
                        logger.info(f"客户端 {client_id} 连接已断开")
                        break
                        
                    # 更新最后活跃时间
                    ws_manager.last_activity[client_id] = datetime.now().timestamp()
                    
                    data_str = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=ws_manager.connection_timeout
                    )
                except asyncio.TimeoutError:
                    # 接收超时，但保持连接，只是记录日志
                    logger.warning(f"客户端 {client_id} 接收消息超时，但保持连接")
                    ws_manager.last_activity[client_id] = datetime.now().timestamp()
                    continue
                except WebSocketDisconnect as e:
                    # 处理客户端断开连接
                    logger.info(f"客户端 {client_id} 主动断开连接")
                    await ws_manager.handle_disconnect(client_id, e.code, "客户端主动断开连接")
                    break
                except Exception as e:
                    if websocket.client_state == WebSocketState.DISCONNECTED:
                        logger.warning(f"客户端 {client_id} 已断开连接: {str(e)}")
                        await ws_manager.handle_disconnect(client_id, 1006, str(e))
                        break
                    else:
                        logger.error(f"接收消息时发生错误: {str(e)}")
                        # 如果是连接相关错误，断开连接
                        if "WebSocket is not connected" in str(e):
                            await ws_manager.handle_disconnect(client_id, 1006, str(e))
                            break
                        continue
                
                try:
                    # 检查连接状态
                    if websocket.client_state == WebSocketState.DISCONNECTED:
                        logger.info(f"客户端 {client_id} 连接已断开")
                        break
                        
                    # 更新最后活跃时间
                    ws_manager.last_activity[client_id] = datetime.now().timestamp()
                    
                    # 解析消息
                    data = json.loads(data_str)

                    # 处理心跳响应
                    if data.get("cmd") == "heartbeat_response":
                        continue

                    # 记录收到的消息
                    logger.info(f"从客户端 {client_id} 收到消息: {data}")

                    # 创建异步任务处理命令
                    await handle_client_command(
                        ws_manager, data, client_id, 
                        scheduler=scheduler, 
                        command_generator=command_generator
                    )

                except json.JSONDecodeError:
                    logger.error(f"无效的JSON消息: {data_str}")
                    error_message = command_generator.generate_message(
                        cmd="error",
                        data={"message": "无效的消息格式，请发送JSON格式"},
                        client_id=client_id
                    )
                    await ws_manager.send_message(client_id, error_message)

        except WebSocketDisconnect as e:
            # 处理客户端断开连接
            logger.info(f"客户端 {client_id} 断开连接")
            await ws_manager.handle_disconnect(client_id, e.code, "客户端断开连接")
        except Exception as e:
            # 处理其他异常
            logger.error(f"处理客户端 {client_id} 消息时发生错误: {str(e)}")
            if client_id:
                await ws_manager.handle_disconnect(client_id, status.WS_1011_INTERNAL_ERROR, str(e))
    except Exception as e:
        logger.error(f"处理WebSocket连接时发生错误: {str(e)}")
        if client_id:
            await ws_manager.disconnect(client_id)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass


async def process_command_with_activity_update(
    ws_manager: WebSocketManager, data: dict, client_id: str, scheduler, command_generator
):
    """处理命令并定期更新活动状态，避免长时间任务导致连接断开"""
    try:
        # 更新最后活跃时间
        ws_manager.last_activity[client_id] = datetime.now().timestamp()
        
        # 创建周期性更新活跃时间的任务
        activity_update_task = asyncio.create_task(
            periodic_activity_update(ws_manager, client_id)
        )
        
        try:
            # 执行命令处理
            await handle_client_command(
                ws_manager, data, client_id, 
                scheduler=scheduler, 
                command_generator=command_generator
            )
        finally:
            # 取消周期性更新任务
            activity_update_task.cancel()
            try:
                await activity_update_task
            except asyncio.CancelledError:
                pass
            
            # 再次更新最后活跃时间
            ws_manager.last_activity[client_id] = datetime.now().timestamp()
    except Exception as e:
        logger.error(f"处理命令时发生错误: {str(e)}")


async def periodic_activity_update(ws_manager: WebSocketManager, client_id: str):
    """周期性更新客户端活跃时间，避免长时间任务导致连接断开"""
    try:
        while True:
            # 更新最后活跃时间
            ws_manager.last_activity[client_id] = datetime.now().timestamp()
            # 每30秒更新一次
            await asyncio.sleep(30)
    except asyncio.CancelledError:
        # 任务被取消，正常退出
        pass
