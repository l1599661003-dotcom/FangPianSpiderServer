import tkinter as tk
import queue
import threading
import asyncio
import json
import time
from typing import Dict, Any
from loguru import logger

from client.app.websocket.WebSocketClient import WebSocketClient
from client.app.core.task_manager import TaskManager
from client.app.core.command_handler import CommandHandler
from client.app.tasks import register_tasks
from client.app.ui.login import LoginPage
from client.app.ui.monitor_app import MonitorApp

class App:
    def __init__(self, master):
        self.master = master
        master.title("爬虫客户端")
        
        # 设置窗口大小
        master.geometry("800x600")
        
        # 初始化日志系统
        self.setup_logger()
        
        # 创建登录页面
        self.login_page = None
        self.main_page = None
        self.token = None
        
        # 初始化任务管理相关对象，登录后才会创建
        self.message_queue = None
        self.websocket_client = None
        self.task_manager = None
        self.command_handler = None
        self.loop = None
        self.websocket_thread = None
        self.message_thread = None
        
        # 标记是否正在运行
        self.running = True
        # 消息处理标志
        self.processing_message = False
        
        # 显示登录页面
        self.login_page = LoginPage(self.master, self.show_main_page)
        
        # 注册窗口关闭事件
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        logger.info("爬虫客户端启动完成")
    
    def show_main_page(self, token):
        """
        显示主界面
        
        Args:
            token: 用户令牌
        """
        # 如果已经有token且和新token相同，则无需重新初始化
        if self.token == token and self.websocket_client and self.websocket_client.connected:
            logger.info("使用现有连接，无需重新初始化")
            # 显示监控界面
            if self.main_page is None:
                self.main_page = MonitorApp(self.master, self.show_login_page, token, self.websocket_client)
            else:
                self.main_page.setup_ui()
            return
        
        # 如果已有其他token的连接，先关闭它
        if self.websocket_client:
            self.cleanup_components()
            # 等待旧连接彻底关闭
            time.sleep(1)
        
        self.token = token
        
        # 初始化各种任务管理组件
        self.initialize_task_components()
        
        # 显示监控界面，传递WebSocket客户端
        if self.main_page is None:
            self.main_page = MonitorApp(self.master, self.show_login_page, token, self.websocket_client)
        else:
            self.main_page.setup_ui()
    
    def show_login_page(self):
        """
        显示登录页面
        """
        # 清理任务管理组件
        self.cleanup_components()
        
        # 显示登录页面
        self.login_page.setup_ui()
    
    def cleanup_components(self):
        """
        清理任务管理组件
        """
        logger.info("开始清理任务管理组件")
        
        # 停止WebSocket客户端
        if self.websocket_client:
            # 停止WebSocket客户端的运行标志
            self.websocket_client.running = False
            
            # 如果已连接，尝试关闭连接
            if self.websocket_client.connected and self.loop:
                try:
                    # 在事件循环中安排关闭任务
                    asyncio.run_coroutine_threadsafe(
                        self.websocket_client.close(),
                        self.loop
                    )
                except Exception as e:
                    logger.error(f"关闭WebSocket连接失败: {e}")
        
        # 停止任务管理器
        if self.task_manager and self.loop:
            try:
                # 在事件循环中安排关闭任务
                asyncio.run_coroutine_threadsafe(
                    self.task_manager.shutdown(),
                    self.loop
                )
            except Exception as e:
                logger.error(f"关闭任务管理器失败: {e}")
        
        # 等待线程结束
        if self.websocket_thread and self.websocket_thread.is_alive():
            # 尝试等待WebSocket线程自行结束
            logger.info("等待WebSocket线程结束")
            self.websocket_thread.join(timeout=1.0)
        
        if self.message_thread and self.message_thread.is_alive():
            # 尝试等待消息处理线程自行结束
            logger.info("等待消息处理线程结束")
            self.message_thread.join(timeout=1.0)
        
        # 清空引用
        self.websocket_client = None
        self.task_manager = None
        self.command_handler = None
        self.message_queue = None
        self.loop = None
        self.websocket_thread = None
        self.message_thread = None
        
        logger.info("任务管理组件清理完成")
    
    def initialize_task_components(self):
        """
        初始化任务管理组件
        """
        logger.info("开始初始化任务管理组件")
        
        # 创建消息队列
        self.message_queue = queue.Queue()
        
        # 创建WebSocket客户端，使用登录获取的token
        self.websocket_client = WebSocketClient(self.token, self.message_queue)
        self.websocket_client.running = True  # 确保运行标志设置为True
        
        # 创建任务管理器
        self.task_manager = TaskManager()
        
        # 创建命令处理器
        self.command_handler = CommandHandler(self.websocket_client, self.task_manager)
        
        # 设置任务管理器的命令处理器引用
        self.task_manager.set_command_handler(self.command_handler)
        
        # 注册任务处理器
        register_tasks(self.task_manager)
        
        # 创建新的事件循环
        self.loop = asyncio.new_event_loop()
        
        # 启动WebSocket连接线程
        self.websocket_thread = threading.Thread(target=self.start_websocket, daemon=True)
        self.websocket_thread.start()
        
        # 启动消息处理线程
        self.message_thread = threading.Thread(target=self.process_messages, daemon=True)
        self.message_thread.start()
        
        logger.info("任务管理组件初始化完成")
    
    def setup_logger(self):
        """设置日志处理器"""
        import os
        log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        logger.info(f"日志路径: {log_path}")
        logger.add("data/logs/monitor_{time}.log", rotation="1 day", retention="7 days", level="INFO")
    
    def start_websocket(self):
        """启动WebSocket连接线程"""
        try:
            # 设置当前线程的事件循环
            asyncio.set_event_loop(self.loop)
            
            # 运行连接协程
            self.loop.run_until_complete(self.websocket_client.connect())
        except Exception as e:
            logger.error(f"WebSocket连接线程异常: {e}")
    
    def process_messages(self):
        """处理接收到的消息线程"""
        try:
            # 设置当前线程的事件循环
            asyncio.set_event_loop(self.loop)
            
            # 使用事件循环方式运行异步处理
            while self.running and self.message_queue and self.command_handler:
                try:
                    # 从队列中获取消息（带超时）
                    try:
                        message = self.message_queue.get(timeout=0.5)
                    except queue.Empty:
                        # 队列为空，继续下一次循环
                        time.sleep(0.1)  # 小暂停避免过度循环
                        continue
                    
                    if message and self.command_handler:
                        # 使用事件循环来处理消息
                        future = asyncio.run_coroutine_threadsafe(
                            self._process_message(message), 
                            self.loop
                        )
                        # 非阻塞方式等待结果
                        future.add_done_callback(lambda f: self._handle_future_result(f))
                    
                    # 标记消息已处理
                    self.message_queue.task_done()
                    
                except Exception as e:
                    logger.error(f"处理消息失败: {e}")
                    time.sleep(1)  # 发生错误时暂停一下
                
        except Exception as e:
            logger.error(f"消息处理线程异常: {e}")
    
    def _handle_future_result(self, future):
        """处理异步任务的结果"""
        try:
            # 获取结果，如果有异常会被捕获
            future.result()
        except Exception as e:
            logger.error(f"异步任务执行失败: {e}")
    
    async def _process_message(self, message):
        """处理单个消息，作为独立任务执行"""
        try:
            # 标记开始处理
            self.processing_message = True
            
            # 尝试处理消息
            await self.command_handler.handle_command(message)
            
        except Exception as e:
            logger.error(f"处理单个消息失败: {e}")
        finally:
            # 标记处理完成
            self.processing_message = False
    
    def on_closing(self):
        """窗口关闭事件处理"""
        logger.info("正在关闭客户端...")
        
        # 设置运行标志为False
        self.running = False
        
        # 清理组件
        self.cleanup_components()
        
        # 等待一段时间确保资源清理
        self.master.after(1000, self.master.destroy)