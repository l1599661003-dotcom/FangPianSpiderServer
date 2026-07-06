import json
import tkinter as tk
from tkinter import ttk, messagebox

# 登录页面
from loguru import logger

from client.app.service.UserLoginService import UserLoginService

class LoginPage:
    def __init__(self, root, show_main_page):
        self.root = root
        self.show_main_page = show_main_page
        self.setup_ui()
        self.login_service = UserLoginService()

        # 加载token
        self.token = self.load_token()
        if self.token:
            self.show_main_page(self.token)

    def setup_ui(self):
        # 清空窗口
        for widget in self.root.winfo_children():
            widget.destroy()

        self.root.title("用户登录")

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 用户名输入框
        ttk.Label(main_frame, text="用户名:").grid(row=0, column=0, padx=5, pady=5)
        self.username_entry = ttk.Entry(main_frame)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)

        # 密码输入框
        ttk.Label(main_frame, text="密码:").grid(row=1, column=0, padx=5, pady=5)
        self.password_entry = ttk.Entry(main_frame, show="*")
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        # 登录按钮
        login_button = ttk.Button(main_frame, text="登录", command=self.login)
        login_button.grid(row=2, column=0, columnspan=2, pady=10)

    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        # 简单模拟登录验证
        flag, token = self.login_service.login(username, password)
        logger.info(f"flag: {flag}", flag)
        if flag:
            self.save_token(token)
            self.show_main_page(token)
        else:
            messagebox.showerror("登录失败", "请输入正确的用户名和密码")

    def on_closing(self):
        self.root.destroy()

    def load_token(self):
        try:
            with open("data/token.json", "r") as f:
                data = json.load(f)
                return data["token"]
        except FileNotFoundError:
            return None

    def save_token(self, token):
        with open("data/token.json", "w") as f:
            json.dump({"token": token}, f)
