from datetime import datetime
from typing import Dict, Any
import asyncio

from loguru import logger

from server.app.core.WebSocketManager import WebSocketManager
from server.app.core.command_generator import CommandGenerator
from server.app.dao.FpOutBloggerCooperatorDao import fp_out_blogger_cooperator_dao
from server.app.dao.FpSpiderBloggerDao import fp_spider_blogger_dao
from server.app.dao.NoteDetailBloggerDao import note_detail_blogger_dao
from server.app.dao.TrainingBloggerDetailsDao import training_blogger_details_dao
from server.app.services.ClientTaskService import client_task_service
from server.app.services.SpiderTaskService import spider_task_service
from server.app.services.TaskService import TaskService, task_service
from server.app.services.TokenService import token_service


async def handle_client_command(websocket_manager: WebSocketManager, command: Dict[str, Any], client_id: str, scheduler=None, command_generator: CommandGenerator = None):
    """处理客户端发送的命令
    
    Args:
        websocket_manager: WebSocket连接管理器
        command: 客户端发送的命令
        client_id: 客户端ID
        scheduler: 任务调度器，通过依赖注入传入
        command_generator: 命令生成器，通过依赖注入传入
    """
    cmd = command.get("cmd")
    data = command.get("data", {})
    
    try:
        # 更新客户端活跃时间
        websocket_manager.last_activity[client_id] = datetime.now().timestamp()
        
        if cmd == "task_status":
            # 处理任务状态更新
            await handle_task_status(websocket_manager, data, client_id, scheduler)
        elif cmd == "log":
            # 处理日志消息
            await handle_log_message(websocket_manager, data, client_id)
        elif cmd == "error":
            # 处理错误消息
            await handle_error_message(websocket_manager, data, client_id, scheduler)
        elif cmd == "action":
            # 处理自定义操作
            await handle_action(websocket_manager, data, client_id, scheduler)
        elif cmd == "token_request":
            # 处理令牌请求
            if command_generator is None:
                logger.error("命令生成器为空，无法处理令牌请求")
                return
            await handle_token_request(websocket_manager, command_generator, command, client_id)
        elif cmd == "token_release":
            task_id = command.get("task_id")
            if not task_id:
                logger.warning(f"令牌释放指令缺少任务ID参数: {command}")
                return
            await handle_token_release(websocket_manager, client_id=client_id, command=command, command_generator=command_generator)
        elif cmd == "data_request":
            # 处理数据请求 - 耗时任务，使用带超时保护的处理
            task_id = command.get("task_id")
            if not task_id:
                logger.warning(f"数据请求缺少任务ID参数: {command}")
                return
            
            if command_generator is None:
                logger.error("命令生成器为空，无法处理数据请求")
                return
            
            # 创建带进度更新的数据请求处理
            await handle_data_request_with_progress(websocket_manager, command_generator, client_id, task_id, command)
        elif cmd == "task_complete":
            # 处理任务完成
            task_id = command.get("task_id")
            if not task_id:
                logger.warning(f"任务完成指令缺少任务ID参数: {command}")
                return
            
            await handle_task_complete(websocket_manager, client_id, task_id, command)
        elif cmd == "result_report":
            # 处理结果上报 - 耗时任务，使用带超时保护的处理
            task_id = command.get("task_id")
            if not task_id:
                logger.warning(f"结果上报指令缺少任务ID参数: {command}")
                return
            
            if command_generator is None:
                logger.error("命令生成器为空，无法处理结果上报")
                return
                
            # 创建带进度更新的结果上报处理
            await handle_result_report_with_progress(websocket_manager, command_generator, client_id, task_id, command)
        else:
            logger.warning(f"未知命令类型: {cmd}")
    except Exception as e:
        logger.error(f"处理客户端命令异常: {e}")


async def handle_task_status(websocket_manager: WebSocketManager, data: Dict[str, Any], client_id: str, scheduler=None):
    """处理任务状态更新
    
    Args:
        websocket_manager: WebSocket连接管理器
        data: 状态数据
        client_id: 客户端ID
        scheduler: 任务调度器，通过依赖注入传入
    """
    task_id = data.get("task_id")
    client_task_id = data.get("client_task_id")
    status = data.get("status")
    progress = data.get("progress", 0)
    
    if not all([task_id, client_task_id, status is not None]):
        logger.warning(f"任务状态更新缺少必要参数: {data}")
        return
    
    try:
        # 更新任务进度
        if scheduler:
            await scheduler.update_execution_progress(client_task_id, progress, status)
        
        # 如果任务已完成或失败，通知调度器
        if status in [2, 3]:  # 2:已完成, 3:已失败
            # 任务结束，从客户端任务列表中移除
            websocket_manager.remove_client_task(client_id, task_id)
            
            # 检查是否所有客户端都已完成
            client_tasks = await client_task_service.get_tasks_by_task_id(task_id)
            all_finished = all(ct.get("status") in [2, 3] for ct in client_tasks)
            
            if all_finished:
                # 所有客户端都已完成，更新任务状态
                await spider_task_service.update_task_status(task_id, 2)  # 2:已完成
                
        logger.info(f"已更新任务状态: {task_id}, 状态: {status}, 进度: {progress}")
        
    except Exception as e:
        logger.error(f"更新任务状态失败: {e}")


async def handle_task_result(websocket_manager: WebSocketManager, data: Dict[str, Any], client_id: str):
    """处理任务结果
    
    Args:
        websocket_manager: WebSocket连接管理器
        data: 结果数据
        client_id: 客户端ID
    """
    task_id = data.get("task_id")
    client_task_id = data.get("client_task_id")
    result = data.get("result")
    
    if not all([task_id, client_task_id]):
        logger.warning(f"任务结果缺少必要参数: {data}")
        return
    
    try:
        # 保存任务结果
        await client_task_service.update_task_result(client_task_id, result)
        logger.info(f"已保存任务结果: {task_id}")
        
    except Exception as e:
        logger.error(f"保存任务结果失败: {e}")


async def handle_log_message(websocket_manager: WebSocketManager, data: Dict[str, Any], client_id: str):
    """处理日志消息
    
    Args:
        websocket_manager: WebSocket连接管理器
        data: 日志数据
        client_id: 客户端ID
    """
    level = data.get("level", "info")
    message = data.get("message", "")
    
    if level == "error":
        logger.error(f"客户端 {client_id} 错误: {message}")
    elif level == "warning":
        logger.warning(f"客户端 {client_id} 警告: {message}")
    else:
        logger.info(f"客户端 {client_id} 日志: {message}")


async def handle_error_message(websocket_manager: WebSocketManager, data: Dict[str, Any], client_id: str, scheduler=None):
    """处理错误消息
    
    Args:
        websocket_manager: WebSocket连接管理器
        data: 错误数据
        client_id: 客户端ID
        scheduler: 任务调度器，通过依赖注入传入
    """
    task_id = data.get("task_id")
    error_msg = data.get("message", "")
    
    logger.error(f"客户端 {client_id} 报告错误: {error_msg}, 任务ID: {task_id}")
    
    if task_id:
        # 如果是任务相关的错误，更新任务状态
        client_task = await client_task_service.get_task_by_client_and_task(client_id, task_id)
        if client_task:
            # 更新任务状态为失败
            await client_task_service.update_task_status(client_task["id"], 3)  # 3:已失败
            
            # 更新执行进度
            if "progress" in data and scheduler:
                await scheduler.update_execution_progress(
                    client_task["id"], 
                    data.get("progress", 0), 
                    3  # 3:已失败
                )


async def handle_action(websocket_manager: WebSocketManager, data: Dict[str, Any], client_id: str, scheduler=None):
    """处理自定义操作
    
    Args:
        websocket_manager: WebSocket连接管理器
        data: 操作数据
        client_id: 客户端ID
        scheduler: 任务调度器，通过依赖注入传入
    """
    action = data.get("action")
    
    if action == "stop_task" and scheduler:
        # 停止任务操作
        task_id = data.get("task_id")
        reason = data.get("reason", "客户端请求停止")
        
        if task_id:
            # 调用停止任务方法
            await scheduler.stop_task(task_id, reason)
            logger.info(f"收到客户端停止任务请求: {task_id}, 原因: {reason}")
            
    elif action == "restart_task" and scheduler:
        # 重启任务操作
        task_id = data.get("task_id")
        
        if task_id:
            # 先停止任务
            await scheduler.stop_task(task_id, "重启任务")
            
            # 然后更新任务状态为运行中
            await spider_task_service.update_task_status(task_id, 1)  # 1:运行中
            
            logger.info(f"收到客户端重启任务请求: {task_id}")
            
    else:
        logger.warning(f"未知操作类型: {action}")


async def handle_data_request_with_progress(websocket_manager: WebSocketManager, command_generator: CommandGenerator, client_id: str, task_id: str, message: Dict[str, Any]):
    """
    处理数据请求指令（带进度更新，防止WebSocket超时）
    
    Args:
        websocket_manager: WebSocket连接管理器
        command_generator: 命令生成器
        client_id: 客户端ID
        task_id: 任务ID
        message: 客户端发送的指令
    """
    try:
        # 周期性更新活跃时间的任务
        activity_update_task = asyncio.create_task(
            _periodic_keep_alive(websocket_manager, client_id, task_id, command_generator)
        )
        try:
            # 获取请求的数据大小
            batch_size = message.get("data", {}).get("batch_size", 100)

            # 发送处理中状态更新
            if command_generator:
                processing_msg = command_generator.generate_message(
                    "processing", 
                    {"message": "正在获取数据", "progress": 10},
                    task_id
                )
                await websocket_manager.send_message(client_id, processing_msg)
            
            # 请求任务数据
            task_service = TaskService()

            data_list, batch_id = await task_service.get_task_data(task_id, client_id, batch_size)

            # 更新处理状态
            if command_generator:
                processing_msg = command_generator.generate_message(
                    "processing", 
                    {"message": "数据获取完成，准备发送", "progress": 80},
                    task_id
                )
                await websocket_manager.send_message(client_id, processing_msg)
            
            # 如果没有数据，发送任务完成指令
            if not data_list:
                task_complete_message = command_generator.generate_message(
                    "task_complete", 
                    {"message": "没有更多数据"},
                    task_id
                )
                await websocket_manager.send_message(client_id, task_complete_message)
                return
            
            # 发送数据推送指令
            data_push_message = command_generator.generate_data_push(task_id, data_list, batch_id)
            await websocket_manager.send_message(client_id, data_push_message)
            
        finally:
            # 取消活跃时间更新任务
            activity_update_task.cancel()
            try:
                await activity_update_task
            except asyncio.CancelledError:
                pass
            
    except Exception as e:
        logger.error(f"处理数据请求失败: {e}, 客户端: {client_id}, 任务: {task_id}")
        # 发送错误消息
        if command_generator:
            error_message = command_generator.generate_error(
                "DATA_REQUEST_ERROR", 
                f"处理数据请求失败: {str(e)}",
                task_id
            )
            await websocket_manager.send_message(client_id, error_message)


async def handle_progress_report(websocket_manager: WebSocketManager, client_id: str, task_id: str, message: Dict[str, Any]):
    """
    处理进度上报指令
    
    Args:
        websocket_manager: WebSocket连接管理器
        client_id: 客户端ID
        task_id: 任务ID
        message: 客户端发送的指令
    """
    try:
        # 获取进度数据
        progress_data = message.get("data", {})
        progress = progress_data.get("progress", 0)
        batch_id = progress_data.get("batch_id")
        
        # 更新任务进度
        task_service = TaskService()
        await task_service.update_task_progress(task_id, client_id, progress, batch_id)
        
        logger.info(f"客户端 {client_id} 任务 {task_id} 进度: {progress}%")
        
    except Exception as e:
        logger.error(f"处理进度上报失败: {e}, 客户端: {client_id}, 任务: {task_id}")


async def handle_error_report(websocket_manager: WebSocketManager, command_generator: CommandGenerator, client_id: str, task_id: str, message: Dict[str, Any]):
    """
    处理错误上报指令
    
    Args:
        websocket_manager: WebSocket连接管理器
        command_generator: 命令生成器
        client_id: 客户端ID
        task_id: 任务ID
        message: 客户端发送的指令
    """
    try:
        # 获取错误数据
        error_data = message.get("data", {})
        error_code = error_data.get("code", "UNKNOWN_ERROR")
        error_message = error_data.get("message", "未知错误")
        batch_id = error_data.get("batch_id")
        
        # 记录错误信息
        task_service = TaskService()
        await task_service.record_task_error(task_id, client_id, error_code, error_message, batch_id)
        
        logger.error(f"客户端 {client_id} 任务 {task_id} 上报错误: [{error_code}] {error_message}")
        
        # 检查是否需要停止任务
        if await task_service.should_stop_task(task_id, error_code):
            # 发送任务停止指令
            stop_message = command_generator.generate_task_stop(
                task_id, 
                f"由于错误停止任务: {error_message}"
            )
            await websocket_manager.send_message(client_id, stop_message)
        
    except Exception as e:
        logger.error(f"处理错误上报失败: {e}, 客户端: {client_id}, 任务: {task_id}")


async def handle_task_complete(websocket_manager: WebSocketManager, client_id: str, task_id: str, message: Dict[str, Any]):
    """
    处理任务完成指令
    
    Args:
        websocket_manager: WebSocket连接管理器
        client_id: 客户端ID
        task_id: 任务ID
        message: 客户端发送的指令
    """
    try:
        # 获取任务完成数据
        complete_data = message.get("data", {})
        
        # 更新任务状态
        task_service = TaskService()
        await task_service.complete_client_task(task_id, client_id, complete_data)
        
        # 移除客户端任务
        websocket_manager.remove_client_task(client_id, task_id)
        
        logger.info(f"客户端 {client_id} 任务 {task_id} 已完成")
        
    except Exception as e:
        logger.error(f"处理任务完成失败: {e}, 客户端: {client_id}, 任务: {task_id}")


async def handle_token_request(websocket_manager: WebSocketManager, command_generator: CommandGenerator, command: Dict[str, Any], client_id: str):
    """
    处理令牌请求指令
    
    Args:
        websocket_manager: WebSocket连接管理器
        command_generator: 命令生成器
        command: 客户端发送的命令
        client_id: 客户端ID
    """
    try:
        # 获取请求参数
        task_id = command.get("task_id")
        data = command.get("data", {})
        platform_id = data.get("platform_id")
        
        if not all([task_id, platform_id]):
            logger.warning(f"令牌请求缺少必要参数: task_id={task_id}, platform_id={platform_id}")
            error_message = command_generator.generate_error(
                "TOKEN_REQUEST_ERROR", 
                "令牌请求缺少必要参数",
                task_id
            )
            await websocket_manager.send_message(client_id, error_message)
            return
        
        # 获取任务日志ID，用于令牌分配
        client_task = await client_task_service.get_task_by_client_and_task(client_id, task_id)
        
        if not client_task:
            logger.warning(f"找不到客户端任务: 客户端ID: {client_id}, 任务ID: {task_id}")
            error_message = command_generator.generate_error(
                "TOKEN_REQUEST_ERROR", 
                "找不到客户端任务",
                task_id
            )
            await websocket_manager.send_message(client_id, error_message)
            return
        
        task_log_id = client_task.get("task_log_id")
        
        # 先检查客户端是否已经分配了令牌
        token_info = await token_service.get_client_token(task_id, client_id)
        success = True
        # 如果已经分配了令牌，直接返回
        if not token_info:
            # 分配令牌
            success, token_info = await token_service.allocate_token(
                task_id=task_id,
                client_id=client_id,
                task_log_id=task_log_id,
                platform_id=platform_id
            )
        
        if not success or not token_info:
            logger.warning(f"无法分配令牌: 客户端ID: {client_id}, 任务ID: {task_id}, 平台ID: {platform_id}")
            error_message = command_generator.generate_error(
                "TOKEN_ALLOCATION_ERROR", 
                "无法分配令牌，可能没有可用的令牌",
                task_id
            )
            await websocket_manager.send_message(client_id, error_message)

            # 同时发送停止任务指令
            stop_message = command_generator.generate_task_stop(
                task_id, 
                f"由于令牌分配失败，停止任务"
            )
            await websocket_manager.send_message(client_id, stop_message)
            return
        
        # 发送令牌响应
        token_response = command_generator.generate_token_response(
            task_id,
            token_info.get("token_id"),
            token_info.get("token_content")
        )
        
        await websocket_manager.send_message(client_id, token_response)
        logger.info(f"为客户端 {client_id} 任务 {task_id} 分配令牌 {token_info.get('token_id')} 成功")
        
    except Exception as e:
        logger.error(f"处理令牌请求失败: {e}, 客户端: {client_id}")
        # 发送错误消息
        if task_id:
            error_message = command_generator.generate_error(
                "TOKEN_REQUEST_ERROR", 
                f"处理令牌请求失败: {str(e)}",
                task_id
            )
            await websocket_manager.send_message(client_id, error_message) 


async def handle_token_release(websocket_manager: WebSocketManager, command_generator: CommandGenerator, command: Dict[str, Any], client_id: str):
    """
    处理令牌释放指令

    Args:
        websocket_manager: WebSocket连接管理器
        command_generator: 命令生成器
        command: 客户端发送的命令
        client_id: 客户端ID
    """
    try:
        # 获取请求参数
        task_id = command.get("task_id")
        data = command.get("data", {})
        platform_id = data.get("platform_id")
        token_status = data.get("status", 1)

        if not all([task_id]):
            logger.warning(f"令牌请求缺少必要参数: task_id={task_id}")
            error_message = command_generator.generate_error(
                "TOKEN_REQUEST_ERROR",
                "令牌请求缺少必要参数",
                task_id
            )
            await websocket_manager.send_message(client_id, error_message)
            return

        # 先检查客户端是否已经分配了令牌
        token_info = await token_service.get_client_token(task_id, client_id)
        # 如果已经分配了令牌，直接返回
        if not token_info:
            # 分配令牌
            return
        success = await token_service.release_token(token_info.get("id", 0))

        if token_status > 1:
            await token_service.update_token_status(token_info.get("id", 0), token_status)
        if not success:
            logger.warning(f"无法分配令牌: 客户端ID: {client_id}, 任务ID: {task_id}, 平台ID: {platform_id}")
            error_message = command_generator.generate_error(
                "TOKEN_ALLOCATION_ERROR",
                "无法分配令牌，可能没有可用的令牌",
                task_id
            )
            await websocket_manager.send_message(client_id, error_message)
            return

    except Exception as e:
        logger.error(f"处理令牌请求失败: {e}, 客户端: {client_id}")
        # 发送错误消息
        if task_id:
            error_message = command_generator.generate_error(
                "TOKEN_REQUEST_ERROR",
                f"处理令牌请求失败: {str(e)}",
                task_id
            )
            await websocket_manager.send_message(client_id, error_message)


async def handle_result_report_with_progress(websocket_manager: WebSocketManager, command_generator: CommandGenerator, client_id: str, task_id: str, message: Dict[str, Any]):
    """
    处理结果上报指令（带进度更新，防止WebSocket超时）
    
    Args:
        websocket_manager: WebSocketManager 连接管理器
        command_generator: 命令生成器
        client_id: 客户端ID
        task_id: 任务ID
        message: 客户端发送的指令
    """
    try:
        # 周期性更新活跃时间的任务
        activity_update_task = asyncio.create_task(
            _periodic_keep_alive(websocket_manager, client_id, task_id, command_generator)
        )
        
        try:
            # 发送处理中状态更新
            if command_generator:
                processing_msg = command_generator.generate_message(
                    "processing", 
                    {"message": "正在处理上报数据", "progress": 10},
                    task_id
                )
                await websocket_manager.send_message(client_id, processing_msg)
                
            # 处理结果上报的原有逻辑
            await handle_result_report(websocket_manager, command_generator, client_id, task_id, message)
                
            # 发送处理完成状态更新
            if command_generator:
                processing_msg = command_generator.generate_message(
                    "processing", 
                    {"message": "数据处理完成", "progress": 100},
                    task_id
                )
                await websocket_manager.send_message(client_id, processing_msg)
                
        finally:
            # 取消活跃时间更新任务
            activity_update_task.cancel()
            try:
                await activity_update_task
            except asyncio.CancelledError:
                pass
                
    except Exception as e:
        logger.error(f"处理结果上报失败: {e}, 客户端: {client_id}, 任务: {task_id}")
        # 发送错误消息
        if command_generator:
            error_message = command_generator.generate_error(
                "RESULT_REPORT_ERROR", 
                f"处理结果上报失败: {str(e)}",
                task_id
            )
            await websocket_manager.send_message(client_id, error_message)


async def _periodic_keep_alive(websocket_manager: WebSocketManager, client_id: str, task_id: str, command_generator: CommandGenerator = None):
    """周期性发送保活消息，避免WebSocket超时"""
    progress = 0
    try:
        while True:
            # 更新连接的最后活跃时间
            websocket_manager.last_activity[client_id] = datetime.now().timestamp()
            
            # 每30秒发送一次进度更新
            if command_generator and task_id:
                # 简单的进度递增（0-90）
                progress = (progress + 10) % 90
                progress_msg = command_generator.generate_message(
                    "progress_update", 
                    {"progress": progress, "message": "任务处理中..."},
                    task_id
                )
                try:
                    await websocket_manager.send_message(client_id, progress_msg)
                    logger.debug(f"发送保活消息到客户端 {client_id}, 任务 {task_id}, 进度 {progress}")
                except Exception as e:
                    logger.warning(f"发送保活消息失败: {e}")
            
            # 等待30秒
            await asyncio.sleep(30)
    except asyncio.CancelledError:
        # 任务被取消，正常退出
        pass


async def handle_result_report(websocket_manager: WebSocketManager, command_generator: CommandGenerator, client_id: str, task_id: str, message: Dict[str, Any]):
    """
    处理结果上报指令
    
    Args:
        websocket_manager: WebSocketManager 连接管理器
        command_generator: 命令生成器
        client_id: 客户端ID
        task_id: 任务ID
        message: 客户端发送的指令
    """
    try:
        # 导入服务类
        from server.app.services.MongoDBService import mongodb_service
        from server.app.services.TaskTypeService import task_type_service

        # 任务客户端分配信息
        client_task = await client_task_service.get_task_by_client_and_task(client_id, task_id)
        # 任务信息
        task = await spider_task_service.get_task_by_id(task_id)
        # 获取任务类型
        task_type = task.get('task_type')
        if not task_type:
            logger.warning(f"无法确定任务类型，将使用默认集合存储: 任务ID: {task_id}")
        # 获取结果数据
        data = message.get("data", { "result": {}})

        logger.info(f"任务类型: {task_type}, 任务ID: {task_id}")
        result = data.get('result', {})
        record_id = data.get("blogger_id", '')
        if result:
            logger.warning(f"结果数据为空，将忽略结果上报: 任务ID: {task_id}")
            result_keys = result.keys()
            success = False
            for key in result_keys:
                logger.info(f"结果数据: 键: {key}")
                key_data = result.get(key, None)
                if not key_data:
                    logger.warning(f"结果数据为空，将忽略结果上报: 任务ID: {task_id}")
                    continue
                # 添加客户端信息和时间戳
                result_data = {
                    "list":  key_data,  # 原始数据
                    "client_id": client_id,
                    "client_task_log_id": client_task.get('task_log_id'),
                    "timestamp": datetime.now().timestamp()
                }
                # 保存到MongoDB
                success = await mongodb_service.save_task_result(task_id, key, result_data)

            if success:
                logger.info(f"已保存客户端 {client_id} 上报的结果数据: 任务ID: {task_id}, 任务类型: {task_type}")

        if record_id and (task_id == "8" or task_id == "11"):
            await training_blogger_details_dao.update_training_blogger_status(record_id)
        if record_id and (task_id == "7" or task_id == "9" or task_id == "10" or task_id == "13"):
            await fp_spider_blogger_dao.update_fp_blogger_status(record_id, task_id, client_id)
        if record_id and task_id == "14":
            await fp_out_blogger_cooperator_dao.update_fp_blogger_status(record_id, task_id, client_id)
        if record_id and task_id == "15":
            await note_detail_blogger_dao.update_note_detail_blogger_status(record_id, task_id, client_id)
            # # 发送确认消息
            # confirm_message = command_generator.generate_message(
            #     "result_confirm",
            #     {"status": "success", "message": "结果数据已接收并保存"},
            #     task_id
            # )
            # await websocket_manager.send_message(client_id, confirm_message)
        else:
            # 发送错误消息
            error_message = command_generator.generate_error(
                "RESULT_SAVE_ERROR", 
                "保存结果数据失败",
                task_id
            )
            # await websocket_manager.send_message(client_id, error_message)
    except Exception as e:
        logger.error(f"处理结果上报失败: {e}, 客户端: {client_id}, 任务: {task_id}")
        # # 发送错误消息
        # if command_generator:
        #     error_message = command_generator.generate_error(
        #         "RESULT_REPORT_ERROR",
        #         f"处理结果上报失败: {str(e)}",
        #         task_id
        #     )
        #     await websocket_manager.send_message(client_id, error_message)