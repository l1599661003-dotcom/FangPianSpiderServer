import json
import os
import time
from datetime import datetime
import sys
from pathlib import Path
import random

import keyboard
from loguru import logger
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from client.app.core.database.mysql_database_manager import MysqlDatabaseManager
from client.app.core.browser_task_base import BrowserTaskBase
from client.app.utils import TimeUtil


class CommentScraperTask(BrowserTaskBase):
    def __init__(self):
        super().__init__()
        self.logger = logger.bind(class_name=self.__class__.__name__)
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        self.base_url = "https://www.douyin.com/"  # 可根据实际网站调整
        self.is_logged_in = False
        self.api_data = {}  # 存储API数据
        self.cookie_file = os.path.join(self.data_dir, 'dy_cookies.json')
        self.progress_file = os.path.join(self.data_dir, 'scraping_progress.json')
        self.db = MysqlDatabaseManager("tibao_2")
        self.comments = []

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

    def random_sleep(self, min_seconds=1, max_seconds=3):
        """随机等待一段时间，模拟人类行为"""
        sleep_time = random.uniform(min_seconds, max_seconds)
        time.sleep(sleep_time)
        return sleep_time

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
            self.random_sleep(2, 3)
            try:
                # 检查是否存在用户头像元素 (根据实际选择器调整)
                user_element = self.page.locator(".ScPBK7Wg.eRChRJCd.ja0bZiHO").is_visible(timeout=5000)
                if user_element:
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
        登录网站
        :return: 是否登录成功
        """
        try:
            if self.is_logged_in:
                logger.info("已处于登录状态")
                return True

            logger.info("开始登录流程...")
            # 访问首页
            self.page.goto(self.base_url)
            self.random_sleep()

            # 等待并点击登录按钮 (根据实际选择器调整)
            logger.info("等待登录按钮出现...")
            login_button = self.page.wait_for_selector("text=登录", timeout=10000)
            if not login_button:
                logger.error("未找到登录按钮")
                return False
            login_button.click()
            self.random_sleep()

            # 等待登录成功
            logger.info("等待扫码登录...")
            try:
                # 等待个人头像出现，表示登录成功 (根据实际选择器调整)
                avatar = self.page.wait_for_selector(".ScPBK7Wg.eRChRJCd.ja0bZiHO", timeout=60000)  # 给用户60秒扫码时间
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

    def scrape_comments(self, url):
        """抓取指定页面的评论信息"""
        try:
            if not self.is_logged_in:
                logger.error("未登录状态，无法抓取数据")
                return None
                
            logger.info(f"开始抓取评论: {url}")
            self.page.goto(url)
            self.random_sleep(3, 5)  # 等待页面加载

            # 1. 点击评论按钮 - 根据提供的class
            try:
                logger.info("点击评论按钮...")
                comment_button = self.page.locator(".qSsCHWSU.GdNlylMd.u4mlHKc5")
                comment_button.click()
                self.random_sleep(2, 3)  # 等待评论抽屉加载
                logger.info("评论抽屉已打开")
            except Exception as e:
                logger.error(f"点击评论按钮出错: {str(e)}")
                return None

            # 2. 从抽屉顶部开始向下滑动，直到评论底部
            try:
                logger.info("开始滚动加载评论...")
                # 查找评论容器 - 需要根据实际网站调整选择器
                # 先尝试查找评论容器，确定有效的选择器
                possible_containers = [
                    ".NRiH5zYY",  # 可能的评论容器选择器1
                    ".comment-list",  # 可能的评论容器选择器2 
                    ".comment-container",  # 可能的评论容器选择器3
                    ".xgplayer-comment"  # 可能的评论容器选择器4
                ]
                
                container_selector = None
                for selector in possible_containers:
                    try:
                        if self.page.locator(selector).count() > 0:
                            container_selector = selector
                            logger.info(f"找到评论容器: {selector}")
                            break
                    except:
                        continue
                
                if not container_selector:
                    logger.error("未找到评论容器，无法滚动加载评论")
                    return None
                
                # 记录已加载的评论数量，用于判断是否已滚动到底部
                last_comment_count = 0
                # 寻找评论项的有效选择器
                possible_comment_selectors = [
                    ".N4QoVj1f",  # 可能的评论项选择器1
                    ".comment-item",  # 可能的评论项选择器2
                    ".comment-entry",  # 可能的评论项选择器3
                    ".iCa4MyDF"  # 可能的评论项选择器4
                ]
                
                comment_selector = None
                for selector in possible_comment_selectors:
                    try:
                        count = self.page.locator(selector).count()
                        if count > 0:
                            comment_selector = selector
                            logger.info(f"找到评论项选择器: {selector}，当前评论数: {count}")
                            break
                    except:
                        continue
                
                if not comment_selector:
                    logger.error("未找到评论项，无法获取评论")
                    return None
                
                current_comment_count = self.page.locator(comment_selector).count()
                
                # 持续滚动直到没有新评论加载
                scroll_count = 0
                max_scroll_attempts = 100  # 最大滚动尝试次数
                
                # 点击展开更多回复按钮的列表，避免重复点击
                clicked_expand_buttons = set()
                
                while current_comment_count > last_comment_count and scroll_count < max_scroll_attempts:
                    last_comment_count = current_comment_count
                    
                    # 模拟人工滚动：每次只滚动一小段距离（100-300像素），而不是直接滚动到底部
                    scroll_distance = random.randint(100, 300)
                    
                    # 获取当前滚动位置
                    current_scroll_position = self.page.evaluate(f"""() => {{
                        const commentContainer = document.querySelector('{container_selector}');
                        return commentContainer ? commentContainer.scrollTop : 0;
                    }}""")
                    
                    # 滚动到新位置 = 当前位置 + 随机距离
                    self.page.evaluate(f"""(scrollDistance) => {{
                        const commentContainer = document.querySelector('{container_selector}');
                        if (commentContainer) {{
                            commentContainer.scrollTop += scrollDistance;
                        }}
                    }}""", scroll_distance)
                    
                    self.random_sleep(0.8, 1.5)  # 模拟人工停顿
                    
                    # 检查当前评论数量
                    current_comment_count = self.page.locator(comment_selector).count()
                    logger.info(f"已加载评论数: {current_comment_count}, 滚动次数: {scroll_count}")
                    
                    # 3. 查找并点击所有"展开回复"按钮
                    # 可能的展开回复按钮选择器
                    possible_expand_selectors = [
                        ".jlqd8usT.comment-reply-expand-btn",  # 可能的展开按钮选择器1
                        ".jlqd8usT.comment-reply-expand-btn",  # 可能的展开按钮选择器2
                    ]
                    
                    # 尝试每个可能的选择器
                    for expand_selector in possible_expand_selectors:
                        try:
                            # 找到所有展开按钮
                            expand_buttons = self.page.locator(expand_selector).all()
                            if len(expand_buttons) > 0:
                                logger.info(f"找到 {len(expand_buttons)} 个展开回复按钮")
                                
                                # 依次点击每个未点击过的按钮
                                for i, btn in enumerate(expand_buttons):
                                    # 生成按钮唯一标识（使用在页面中的位置）
                                    btn_position = self.page.evaluate("""(index, selector) => {
                                        const elements = document.querySelectorAll(selector);
                                        if (elements[index]) {
                                            const rect = elements[index].getBoundingClientRect();
                                            return `${rect.x},${rect.y}`;
                                        }
                                        return null;
                                    }""", i, expand_selector)
                                    
                                    # 如果按钮未点击过，则点击
                                    if btn_position and btn_position not in clicked_expand_buttons:
                                        try:
                                            logger.info(f"点击第 {i+1} 个展开回复按钮")
                                            # 确保按钮在可视范围内
                                            btn.scroll_into_view_if_needed()
                                            self.random_sleep(0.5, 1)
                                            btn.click()
                                            clicked_expand_buttons.add(btn_position)
                                            self.random_sleep(1, 2)  # 等待回复加载
                                        except Exception as e:
                                            logger.error(f"点击展开回复按钮出错: {str(e)}")
                        except Exception as e:
                            continue
                    
                    # 检查是否有用户中断
                    if keyboard.is_pressed('ctrl+c'):
                        logger.info("检测到中断信号，停止滚动")
                        break
                        
                    scroll_count += 1
                    
                    # 随机暂停，模拟真实人工浏览行为
                    if random.random() < 0.1:  # 10%概率进行较长暂停
                        self.random_sleep(2, 4)
                
                if scroll_count >= max_scroll_attempts:
                    logger.info("达到最大滚动次数，停止滚动")
                elif current_comment_count == last_comment_count:
                    logger.info("评论已全部加载完毕")
                    
                # 记录展开按钮点击统计
                logger.info(f"共点击了 {len(clicked_expand_buttons)} 个展开回复按钮")
                
                return True
                
            except Exception as e:
                logger.error(f"滚动加载评论出错: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"抓取评论出错: {str(e)}")
            return None

    def _extract_comments(self, comment_selector):
        """提取页面上的评论信息 - 根据需求不再提取评论内容"""
        logger.info("根据需求不提取评论内容")
        pass

    def save_comments_to_file(self, filename=None):
        """将评论数据保存到文件 - 根据需求不再需要保存评论"""
        logger.info("根据需求不保存评论内容")
        return True

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
                
            logger.info("浏览器和Playwright已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器时出错: {str(e)}")

    def _handle_api_response(self, response):
        """处理API响应"""
        try:
            if any(keyword in url for keyword in [
                '/aweme/v1/web/comment/list/',
            ]):
                response_text = response.text()
                if response_text:
                    response_data = json.loads(response_text)
                    self._handle_comment_api_response(response_data)
        except Exception as e:
            pass  # 忽略处理异常

    def _handle_comment_api_response(self, response_data):
        """处理评论API的响应数据"""
        # 根据实际API响应结构解析
        try:
            # 这里需要根据实际API响应结构进行调整
            if "comments" in response_data:
                for comment in response_data["comments"]:
                    comment_data = {
                        "username": comment.get("user", {}).get("nickname", ""),
                        "content": comment.get("text", ""),
                        "time": comment.get("create_time", ""),
                        "likes": comment.get("like_count", 0)
                    }
                    if comment_data not in self.comments:
                        self.comments.append(comment_data)
        except Exception as e:
            logger.error(f"处理评论API响应出错: {str(e)}")

    def _save_cookies(self):
        """保存Cookie到文件"""
        try:
            cookies = self.context.cookies()
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f)
            logger.info(f"Cookie已保存到 {self.cookie_file}")
            return True
        except Exception as e:
            logger.error(f"保存Cookie出错: {str(e)}")
            return False

    def _load_cookies(self):
        """从文件加载Cookie"""
        try:
            if not os.path.exists(self.cookie_file):
                logger.info("Cookie文件不存在")
                return False
            
            with open(self.cookie_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            self.context.add_cookies(cookies)
            logger.info(f"已从 {self.cookie_file} 加载Cookie")
            return True
        except Exception as e:
            logger.error(f"加载Cookie出错: {str(e)}")
            return False

    def update_monitor_status(self, status=None, user_id=None, total_count=None, completed_count=None, fail_count=None):
        """更新监控状态"""
        if status:
            self.monitor_data['status'] = status
        if user_id:
            self.monitor_data['user_id'] = user_id
        if total_count is not None:
            self.monitor_data['total_count'] = total_count
        if completed_count is not None:
            self.monitor_data['completed_count'] = completed_count
        if fail_count is not None:
            self.monitor_data['fail_count'] = fail_count
            
        if total_count is not None and completed_count is not None and total_count > 0:
            self.monitor_data['process'] = round((completed_count / total_count) * 100, 2)
        
        logger.info(f"监控状态更新: {self.monitor_data}")


# 示例使用
if __name__ == "__main__":
    scraper = CommentScraperTask()
    try:
        if scraper.login():
            # 抓取指定页面的评论
            url = "https://www.douyin.com/video/YOUR_VIDEO_ID"  # 替换为实际视频URL
            comments = scraper.scrape_comments(url)
            if comments:
                scraper.save_comments_to_file()
    finally:
        scraper.close() 