import json
import os
import time
from datetime import datetime
import sys
from pathlib import Path

import keyboard
from loguru import logger
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from client.app.core.database.mysql_database_manager import MysqlDatabaseManager
from client.app.core.browser_task_base import BrowserTaskBase
from client.app.utils import TimeUtil

# 抖音评论任务


class DyCommentTask(BrowserTaskBase):
    def __init__(self):
        super().__init__()
        self.logger = logger.bind(class_name=self.__class__.__name__)
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        self.base_url = "https://www.douyin.com/"
        self.is_logged_in = False
        self.api_data = {}  # 存储API数据
        self.cookie_file = os.path.join(self.data_dir, 'dy_cookies.json')
        self.progress_file = os.path.join(self.data_dir, 'scraping_progress.json')
        self.db = MysqlDatabaseManager("tibao_2")

        # 设置Playwright驱动路径
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = self.get_playwright_driver_path()

        # 确保驱动目录存在
        driver_path = self.get_playwright_driver_path()
        if not os.path.exists(driver_path):
            os.makedirs(driver_path, exist_ok=True)

        self.setup_browser()
        self.notes = []
        self.stopScroll = False
        self.monitor_data = {
            'fail_count': 0,
            'total_count': 0,
            'completed_count': 0,
            'process': 0
        }

    def get_executable_path(self):
        """获取可执行文件路径"""
        if getattr(sys, 'frozen', False):
            # 如果是打包后的exe
            return os.path.dirname(sys.executable)
        else:
            # 如果是开发环境
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def get_playwright_driver_path(self):
        """获取Playwright驱动路径"""
        if getattr(sys, 'frozen', False):
            # 如果是打包后的exe
            return os.path.join(self.get_executable_path(), '.cache', 'ms-playwright')
        else:
            # 如果是开发环境
            return os.path.join(Path.home(), '.cache', 'ms-playwright')

    def setup_browser(self):
        """初始化浏览器"""
        self.playwright = sync_playwright().start()
        # 配置浏览器选项
        self.browser = self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-gpu',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        # 创建上下文
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 960},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )

        # 尝试加载已保存的Cookie
        if self._load_cookies():
            # 验证Cookie是否有效
            self.page = self.context.new_page()
            self.page.goto(self.base_url)
            TimeUtil.random_sleep(2, 3)
            try:
                # 检查是否存在用户头像元素
                userSide = self.page.locator(".ScPBK7Wg.eRChRJCd.ja0bZiHO").all()
                logger.info(f"user: {len(userSide)}")
                user_len = len(userSide)
                if user_len > 1 or self.page.locator(".ScPBK7Wg.eRChRJCd.ja0bZiHO").is_visible(timeout=50000):
                    self.is_logged_in = True
                    logger.info("Cookie有效，已自动登录")
                else:
                    logger.info("Cookie已失效，需要重新登录")
            except:
                logger.info("Cookie已失效，需要重新登录")
        else:
            self.page = self.context.new_page()

        # 设置页面超时时间
        self.page.set_default_timeout(20000)
        # 设置响应监听
        self.page.on("response", self._handle_api_response)

    def login(self):
        """
        使用扫码方式登录小红书
        :return: 是否登录成功
        """
        try:
            if self.is_logged_in:
                logger.info("已处于登录状态")
                return True

            logger.info("开始登录流程...")
            # 访问首页
            self.page.goto(self.base_url)
            TimeUtil.random_sleep(1, 1)

            # 等待并点击登录按钮
            logger.info("等待登录按钮出现...")
            login_button = self.page.wait_for_selector("text=登录", timeout=10000)
            if not login_button:
                logger.error("未找到登录按钮")
                return False
            login_button.click()
            TimeUtil.random_sleep()

            # 等待扫码登录界面加载
            logger.info("等待扫码登录界面加载...")
            qr_code = self.page.wait_for_selector(".qrcode-img", timeout=10000)
            if not qr_code:
                logger.error("未找到二维码")
                return False

            # 获取二维码图片
            qr_src = qr_code.get_attribute("src")
            if not qr_src:
                logger.error("未获取到二维码图片地址")
                return False

            # 等待登录成功
            logger.info("等待扫码登录...")
            try:
                # 等待个人头像出现，表示登录成功
                avatar = self.page.wait_for_selector(".channel-list >> .user", timeout=60000)  # 给用户60秒扫码时间
                if avatar:
                    logger.info("登录成功！")
                    self.is_logged_in = True

                    # 登录成功后保存Cookie
                    self._save_cookies()

                    return True
                else:
                    logger.error("登录失败，未检测到登录成功状态")
                    return False
            except PlaywrightTimeoutError:
                logger.error("登录超时，请重试")
                return False

        except Exception as e:
            logger.error(f"登录过程出现异常: {str(e)}")
            return False

    def scrape_user_notes(self, user):
        """抓取指定用户的笔记信息"""
        try:
            if not self.is_logged_in:
                logger.error("未登录状态，无法抓取数据")
                self.update_monitor_status(
                    status="未登录",
                    user_id=user.get("nickname"),
                )
                return None
            user_url = user.get('xhs_url')
            self.page.goto(user_url)
            TimeUtil.random_sleep()

            completed = False
            try:
                seeds = set()
                try:
                    # 获取笔记首页笔记列表
                    notes = self.page.locator(".note-item").all()
                    if len(notes) == 0:
                        logger.info("未找到笔记列表，可能已抓取完毕")
                        return None

                    for di, index in notes:
                        di = self.page.locator(f"[data-index='{index - 1}']")
                        logger.info(f"正在抓取第 {index} data-index: {di} 条笔记")
                        seeds.add(di)
                        di.scroll_into_view_if_needed(timeout=5000)
                        di.click()
                        # 停顿1秒
                        time.sleep(1)

                        # # 关闭蒙版页面
                        self.page.keyboard.press('Escape')
                        TimeUtil.random_sleep(1, 1)

                        # 如果发生异常，保存当前进度
                        if keyboard.is_pressed('ctrl+c'):
                            logger.info("检测到中断信号，保存进度后退出")
                            self._save_cookies()
                            self.update_monitor_status(status="已中断")
                            break
                        completed = True
                except Exception as e:
                    logger.error(f"抓取数据完成: {e}")

            except Exception as e:
                logger.error(f"抓取过程出错: {str(e)}")
                self.update_monitor_status(
                    status="出错",
                    fail_count=self.monitor_data.get('fail_count', 0) + 1
                )
                # 保存进度和Cookie
                self._save_cookies()
                completed = False

            # 任务完成后清除进度文件
            if os.path.exists(self.progress_file):
                os.remove(self.progress_file)
            TimeUtil.random_sleep(1, 1)
            return completed

        except Exception as e:
            logger.error(f"抓取用户 {user.get('nickname')} 笔记时出错: {str(e)}")
            self.update_monitor_status(
                status="出错",
                fail_count=self.monitor_data.get('fail_count', 0) + 1
            )
            return None

    def close(self):
        """
        关闭浏览器和playwright
        """
        try:
            # 保存Cookie
            if self.is_logged_in:
                self._save_cookies()

            if hasattr(self, 'page'):
                self.page.close()
            if hasattr(self, 'context'):
                self.context.close()
            if hasattr(self, 'browser'):
                self.browser.close()
            if hasattr(self, 'playwright'):
                self.playwright.stop()
            logger.info("浏览器和playwright已关闭")
        except Exception as e:
            logger.error(f"关闭资源时出错: {str(e)}")

    def _handle_api_response(self, response):
        """处理API响应"""
        try:
            url = response.url
            if any(keyword in url for keyword in [
                '/api/sns/web/v1/feed',
            ]):
                response_data = response.json()
                self.api_data[url] = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'data': response_data
                }
                self._handle_feed_api_response(response_data)
            if any(keyword in url for keyword in [
                '/api/sns/web/v1/user_posted'
            ]):
                response_data = response.json()
                # self._handle_user_posted_api_response(response_data)
        except Exception as e:
            logger.error(f"处理API响应时出错: {str(e)}")
            logger.error(f"响应URL: {url}")
            logger.error(f"响应内容: {response_data if 'response_data' in locals() else '未获取到响应数据'}")

    def _handle_feed_api_response(self, response_data):
        if response_data:
            code = response_data.get('code')
            data = response_data.get('data', {})
            if code == 0:
                items = data.get('items', [])
                for item in items:
                    note_card = item.get('note_card', {})
                    if note_card:
                        user_info = note_card.get('user', {})
                        interact_info = note_card.get('interact_info', {})

                        # 保存用户数据
                        user_data = {
                            'user_id': user_info.get('user_id', ''),
                            'nickname': user_info.get('nickname', ''),
                            'avatar': user_info.get('avatar', '')
                        }
                        self.db.save_user(user_data)

                        # 保存笔记数据
                        note_data = {
                            'note_id': note_card.get('note_id', ''),
                            'user_id': user_info.get('user_id', ''),
                            'nickname': user_info.get('nickname', ''),
                            'title': note_card.get('title', ''),
                            'desc': note_card.get('desc', ''),
                            'liked_count': interact_info.get('liked_count', 0),
                            'collected_count': interact_info.get('collected_count', 0),
                            'comment_count': interact_info.get('comment_count', 0),
                            'share_count': interact_info.get('share_count', 0),
                            'last_update_time': note_card.get('last_update_time', ''),
                            'last_sync_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        self.db.save_note(note_data)
            else:
                logger.warning(f"API响应异常，状态码: {code}")

    def _handle_user_posted_api_response(self, response_data):
        list = response_data.get('data').get('notes')
        self.notes.extend(list)
        self.monitor_data['total_count'] = len(self.notes)
        logger.info(f"_handle_user_posted_api_response items: {len(response_data.get('data').get('notes'))}")

    def _save_cookies(self):
        """
        保存当前会话的Cookie
        """
        try:
            cookies = self.context.cookies()
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f)
            logger.info("Cookie数据已保存")
        except Exception as e:
            logger.error(f"保存Cookie时出错: {str(e)}")

    def _load_cookies(self):
        """
        加载保存的Cookie
        :return: 是否成功加载Cookie
        """
        try:
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                self.context.add_cookies(cookies)
                logger.info("已加载保存的Cookie")
                return True
            return False
        except Exception as e:
            logger.error(f"加载Cookie时出错: {str(e)}")
            return False

    def _save_progress(self, user_id, processed_notes):
        """
        保存抓取进度
        :param user_id: 用户ID
        :param processed_notes: 已处理的笔记列表
        """
        try:
            progress_data = {
                'user_id': user_id,
                'processed_notes': processed_notes,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f)
            logger.info(f"进度已保存: 用户{user_id}, 已处理{len(processed_notes)}条笔记")
        except Exception as e:
            logger.error(f"保存进度时出错: {str(e)}")

    def _load_progress(self):
        """
        加载抓取进度
        :return: (user_id, processed_notes) 或 (None, None)
        """
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                logger.info(f"已加载进度: 用户{progress['user_id']}, 已处理{len(progress['processed_notes'])}条笔记")
                return progress['user_id'], progress['processed_notes']
            return None, None
        except Exception as e:
            logger.error(f"加载进度时出错: {str(e)}")
            return None, None
