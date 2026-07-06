import tkinter as tk

from dotenv import load_dotenv

from client.app.ui.app import App


# 启动应用
def start():
    # 加载环境变量
    load_dotenv()

    # # 初始化数据库
    # data_dir = Path("data")
    # data_dir.mkdir(exist_ok=True)

    # 启动监控界面
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)  # 注册窗口关闭事件
    root.mainloop()

if __name__ == "__main__":
    start()
