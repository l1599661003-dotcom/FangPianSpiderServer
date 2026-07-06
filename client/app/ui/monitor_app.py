import asyncio
import datetime
import json
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, scrolledtext, messagebox

from loguru import logger

from client.app.service.AccountNoteService import AccountNoteService
from client.app.tasks.xhs_notes import XhsNoteTask
from client.app.utils import TimeUtil
from client.app.websocket.WebSocketClient import WebSocketClient


class MonitorApp:
    def __init__(self, root, show_login_page, token, websocket_client=None):
        self.show_login_page = show_login_page
        self.access_token = token

        self.root = root
        self.root.title("爬虫监控")
        self.root.geometry("800x600")

        # 创建数据目录
        self.data_dir = Path("./data")
        self.data_dir.mkdir(exist_ok=True)

        # 初始化数据库和爬虫
        self.note_service = AccountNoteService()
        self.spider = None
        self.spider_thread = None
        self.is_running = False
        self.update_thread = None
        self.last_update_time = 0
        self.update_interval = 1.0  # 更新间隔（秒）

        # 专辑名称
        self.folder_name = tk.StringVar()
        self.group_value = tk.StringVar()

        # 初始化更新队列
        self.update_queue = queue.Queue()
        self.running = True
        self.running_user = None
        self.padding_user = []
        self.group_users = None
        self.group_options = ['请选择']
        self.sleep_time = 3  # 停顿三秒
        groups = self.note_service.list_media_account_group_names()
        logger.info(f"groups: {groups}")
        if groups:
            self.group_options.extend([row.get('group_name', '无') for row in groups])
            self.group_value.set(self.group_options[0])
            self.sleep_time = groups[0].get('sleep_time', 3)

        # WebSocket连接状态
        self.ws_connected = False

        self.setup_ui()
        # 启动更新线程
        self.start_update_thread()

        # 使用已存在的WebSocket客户端或创建新的（通常应使用已存在的）
        if websocket_client:
            self.ws_client = websocket_client
            self.message_queue = websocket_client.message_queue
            logger.info("使用App中已创建的WebSocket客户端")
            self.ws_thread = None  # 不需要新的线程
        else:
            # 仅在没有提供现有客户端时创建新的（兼容旧代码）
            logger.warning("未提供WebSocket客户端，创建新的客户端")
            self.message_queue = queue.Queue()
            self.ws_client = WebSocketClient(token, self.message_queue)
            
            # 启动 WebSocket 客户端线程
            self.ws_thread = threading.Thread(target=self.ws_client.start, daemon=True)
            self.ws_thread.start()

        # 注册WebSocket状态回调
        self.ws_client.set_status_callback(self.on_ws_status_changed)

        # 定时检查队列中的服务端消息
        self.root.after(100, self.check_messages)

    def on_ws_status_changed(self, connected):
        """WebSocket连接状态变更回调"""
        self.ws_connected = connected
        # 使用UI线程更新状态显示
        self.root.after(0, self.update_ws_status)
        
    def update_ws_status(self):
        """更新WebSocket连接状态显示"""
        if hasattr(self, 'ws_status_label'):
            if self.ws_connected:
                self.ws_status_label.config(text="已连接", foreground="green")
                self.add_log("服务器连接已建立")
            else:
                self.ws_status_label.config(text="未连接", foreground="red")
                self.add_log("服务器连接已断开，正在尝试重连...")

    def setup_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 控制按钮区域
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", padding="5")
        control_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        self.folder_input = ttk.OptionMenu(control_frame, self.group_value, *self.group_options)
        self.folder_input.grid(row=0, column=0, padx=5)

        self.start_button = ttk.Button(control_frame, text="开始抓取", command=self.start_spider)
        self.start_button.grid(row=0, column=1, padx=5)

        self.stop_button = ttk.Button(control_frame, text="停止抓取", command=self.stop_spider, state='disabled')
        self.stop_button.grid(row=0, column=2, padx=5)
        
        # 添加WebSocket连接状态显示
        ttk.Label(control_frame, text="服务器:").grid(row=0, column=3, padx=5)
        self.ws_status_label = ttk.Label(control_frame, text="未连接", foreground="red")
        self.ws_status_label.grid(row=0, column=4, padx=5)
        
        # 初始状态同步
        if hasattr(self, 'ws_client') and self.ws_client and self.ws_client.connected:
            self.ws_status_label.config(text="已连接", foreground="green")

        # 任务状态区域
        status_frame = ttk.LabelFrame(main_frame, text="任务状态", padding="5")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(status_frame, text="用户ID:").grid(row=0, column=0, sticky=tk.W)
        self.user_id_label = ttk.Label(status_frame, text="-")
        self.user_id_label.grid(row=0, column=1, sticky=tk.W)

        ttk.Label(status_frame, text="状态:").grid(row=1, column=0, sticky=tk.W)
        self.status_label = ttk.Label(status_frame, text="-")
        self.status_label.grid(row=1, column=1, sticky=tk.W)

        # 进度条
        ttk.Label(status_frame, text="进度:").grid(row=2, column=0, sticky=tk.W)
        self.progress_bar = ttk.Progressbar(status_frame, length=300, mode='determinate')
        self.progress_bar.grid(row=2, column=1, sticky=(tk.W, tk.E))

        # 统计信息区域
        stats_frame = ttk.LabelFrame(main_frame, text="统计信息", padding="5")
        stats_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(stats_frame, text="已处理笔记:").grid(row=0, column=0, sticky=tk.W)
        self.processed_label = ttk.Label(stats_frame, text="0")
        self.processed_label.grid(row=0, column=1, sticky=tk.W)

        ttk.Label(stats_frame, text="总笔记数:").grid(row=1, column=0, sticky=tk.W)
        self.total_label = ttk.Label(stats_frame, text="0")
        self.total_label.grid(row=1, column=1, sticky=tk.W)

        ttk.Label(stats_frame, text="成功数:").grid(row=2, column=0, sticky=tk.W)
        self.success_label = ttk.Label(stats_frame, text="0")
        self.success_label.grid(row=2, column=1, sticky=tk.W)

        ttk.Label(stats_frame, text="失败数:").grid(row=3, column=0, sticky=tk.W)
        self.fail_label = ttk.Label(stats_frame, text="0")
        self.fail_label.grid(row=3, column=1, sticky=tk.W)

        ttk.Label(stats_frame, text="运行时长:").grid(row=4, column=0, sticky=tk.W)
        self.runtime_label = ttk.Label(stats_frame, text="00:00:00")
        self.runtime_label.grid(row=4, column=1, sticky=tk.W)

        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding="5")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 配置grid权重
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)

    def start_update_thread(self):
        """启动更新线程"""

        def update_loop():
            while self.running:
                try:
                    current_time = time.time()
                    # 检查是否达到更新间隔
                    if current_time - self.last_update_time >= self.update_interval:
                        self.last_update_time = current_time
                        # 获取状态数据
                        status_data = self.get_status_data()
                        self.update_queue.put(status_data)
                    time.sleep(1)  # 短暂休眠，避免CPU占用过高
                except Exception as e:
                    logger.error(f"更新线程错误: {e}")

        self.update_thread = threading.Thread(target=update_loop, daemon=True)
        self.update_thread.start()

        # 启动UI更新
        self.process_updates()

    def get_status_data(self):
        """获取状态数据"""
        try:
            status_data = {
                'pending_count': len(self.padding_user),
                'running_count': 0,
                'running_users': self.running_user
            }

            # 如果爬虫在运行，添加爬虫状态
            if self.spider and hasattr(self.spider, 'monitor_data'):
                status_data.update(self.spider.monitor_data)
            return status_data
        except Exception as e:
            logger.error(f"获取状态数据错误: {e}")
            return {}

    def process_updates(self):
        """处理更新队列中的数据"""
        try:
            while True:
                try:
                    data = self.update_queue.get_nowait()
                    self.update_ui(data)
                except queue.Empty:
                    break
        finally:
            # 使用较短的间隔检查更新
            self.root.after(100, self.process_updates)

    def update_ui(self, data):
        """更新UI显示"""
        try:
            # 更新状态显示
            if self.running_user:
                self.user_id_label.config(text=f"名称：{self.running_user['nickname']}，ID：{self.running_user['id']}")
                # self.status_label.config(text=user['status'])
            else:
                self.user_id_label.config(text="-")
                self.status_label.config(text="空闲")

            # 更新按钮状态
            if self.is_running:
                self.start_button.config(state='disabled')
                self.stop_button.config(state='normal')
                if hasattr(self, 'start_time') and self.start_time:
                    elapsed_time = datetime.datetime.now() - self.start_time
                    self.runtime_label.config(text=str(elapsed_time).split('.')[0])
            else:
                self.start_button.config(state='normal')
                self.stop_button.config(state='disabled')

            # 更新进度信息
            if self.spider and hasattr(self.spider, 'monitor_data'):
                total = self.spider.monitor_data.get('total_count', 0)
                completed = self.spider.monitor_data.get('completed_count', 0)
                if total > 0:
                    progress = round((completed / total) * 100, 2)
                    self.progress_bar['value'] = progress
                    self.processed_label.config(text=str(completed))
                    self.total_label.config(text=str(total))
                    self.success_label.config(text=str(completed))

        except Exception as e:
            logger.error(f"更新UI错误: {e}")

    def add_log(self, message):
        """添加日志"""
        try:
            self.log_text.insert(tk.END, f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
            self.log_text.see(tk.END)
            # 限制日志行数
            if int(self.log_text.index('end-1c').split('.')[0]) > 1000:
                self.log_text.delete('1.0', '2.0')
        except Exception as e:
            logger.error(f"添加日志错误: {e}")

    def start_spider(self):
        """开始抓取"""
        if not self.ws_connected:
            messagebox.showwarning("警告", "服务器连接未建立，请等待自动重连或重新登录")
            return
            
        # 检查是否选择了分组
        group_name = self.group_value.get()
        if group_name == '请选择':
            messagebox.showwarning("警告", "请先选择一个分组")
            return
            
        if self.spider is not None:
            return
        account_ids = self.note_service.list_media_account_group_accounts(self.group_value.get())
        ids = [group.get('dandelion_platform_id', '0') for group in account_ids]
        logger.info(f"开始抓取用户{ids}")

        def run_spider():
            self.is_running = True
            self.spider = XhsNoteTask(account_ids[0])
            self.start_time = datetime.datetime.now()
            try:
                self.add_log("开始登录...")
                if not self.spider.login():
                    messagebox.showerror("错误", "登录失败")
                    return
                self.add_log("登录成功")

                while self.is_running:
                    if not ids or len(ids) == 0:
                        TimeUtil.random_sleep(1, 1)
                        continue
                    self.padding_user = self.note_service.get_kol_media_accounts(ids)
                    if not self.padding_user:
                        self.add_log("没有待抓取的用户")
                        break

                    for user in self.padding_user:
                        if not self.is_running:
                            break
                        self.running_user = user
                        nickname = user['nickname']
                        try:
                            self.add_log(f"开始抓取用户: {nickname}")
                            result = self.spider.scrape_user_notes(user, self.sleep_time)
                            if result:
                                self.add_log(f"用户 {nickname} 抓取成功")
                            else:
                                self.add_log(f"用户 {nickname} 抓取失败")
                            self.add_log(f"用户 {nickname} 抓取完成")
                        except Exception as e:
                            self.add_log(f"抓取用户 {nickname} 失败: {str(e)}")

                    self.stop_spider()
            except Exception as e:
                self.add_log(f"爬虫运行错误: {str(e)}")
                messagebox.showerror("错误", f"爬虫运行错误: {str(e)}")
            finally:
                if self.spider:
                    self.spider.close()
                    self.spider = None
                self.is_running = False
                self.add_log("爬虫已停止")

        self.spider_thread = threading.Thread(target=run_spider, daemon=True)
        self.spider_thread.start()

    def stop_spider(self):
        self.add_log("正在停止爬虫...")
        self.is_running = False
        if self.spider:
            self.spider.close()
            self.spider = None
        self.add_log("爬虫已停止")

    def check_messages(self):
        """检查WebSocket消息队列"""
        try:
            # 检查队列是否有消息
            while not self.message_queue.empty():
                message = self.message_queue.get_nowait()
                
                # 根据消息类型进行处理
                if isinstance(message, dict):
                    cmd = message.get('cmd', '')
                    
                    if cmd == 'task_result':
                        # 处理任务结果
                        data = message.get('data', {})
                        task_id = data.get('task_id')
                        result = data.get('result')
                        status = data.get('status')
                        
                        # 记录日志
                        log_message = f"任务 {task_id} 完成，状态: {status}"
                        self.add_log(log_message)
                    
                    elif cmd == 'system_message':
                        # 处理系统消息
                        data = message.get('data', {})
                        content = data.get('content', '')
                        self.add_log(f"系统消息: {content}")
        except Exception as e:
            logger.error(f"处理WebSocket消息异常: {e}")
        finally:
            # 继续定时检查
            self.root.after(100, self.check_messages)

    def on_closing(self):
        self.stop_spider()
        self.running = False
        self.root.destroy()