import os
import pickle
import random
import time
from datetime import datetime

import keyboard
# 导入数据库管理器 - 修正路径
from client.app.core.database.mysql_database_manager import MysqlDatabaseManager
from loguru import logger
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class SeleniumCommentScraper:
    def __init__(self):
        self.logger = logger.bind(class_name=self.__class__.__name__)
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        self.base_url = "https://www.douyin.com/"
        self.is_logged_in = True
        self.cookie_file = os.path.join(self.data_dir, 'selenium_cookies.pkl')
        self.browser_cookie_file = os.path.join(self.data_dir, 'selenium_browser_cookies.json')
        self.db = MysqlDatabaseManager("tibao_2")
        self.url = ''
        # 监控数据
        self.monitor_data = {
            'fail_count': 0,
            'total_count': 0,
            'completed_count': 0,
            'process': 0
        }
        
        # 初始化浏览器
        self.setup_browser()
        
    def random_sleep(self, min_seconds=1, max_seconds=3):
        """随机等待一段时间，模拟人类行为"""
        sleep_time = random.uniform(min_seconds, max_seconds)
        time.sleep(sleep_time)
        return sleep_time
    
    def setup_browser(self):
        """初始化Selenium浏览器"""
        try:
            # 配置Chrome选项
            chrome_options = Options()
            
            # 使用物理机已安装的Chrome
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # 绕过检测
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            # 指定已有的 Chrome 用户数据目录
            chrome_options.add_argument("user-data-dir=C:/Users/asus/AppData/Local/Google/Chrome/User Data")

            # 指定 Chrome 的配置文件（比如"默认"）
            chrome_options.add_argument("profile-directory=Default")
            
            # 添加User-Agent
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
            chrome_options.add_argument('--enable-unsafe-swiftshader')

            # 可选：设置为无头模式（测试时建议注释掉）
            # chrome_options.add_argument("--headless")
            
            # 使用默认的Chrome可执行文件
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_window_size(1280, 960)
            
            # 设置隐式等待时间
            self.driver.implicitly_wait(5)
            
            # 添加性能日志监听
            self.enable_network_logging()
            
            # 尝试加载已保存的Cookie
            if self._load_cookies():
                # 验证Cookie是否有效
                self.driver.get(self.base_url)
                self.random_sleep(2, 3)
                try:
                    # 检查是否存在用户头像元素
                    user_element = WebDriverWait(self.driver, 5).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, ".ScPBK7Wg.eRChRJCd.ja0bZiHO"))
                    )
                    if user_element:
                        self.is_logged_in = True
                        logger.info("Cookie有效，已自动登录")
                    else:
                        logger.info("Cookie已失效，需要重新登录")
                except (TimeoutException, NoSuchElementException):
                    logger.info("Cookie已失效，需要重新登录")
            
            logger.info("Selenium浏览器初始化成功")
            
        except Exception as e:
            logger.error(f"初始化Selenium浏览器出错: {str(e)}")
            raise
    
    def enable_network_logging(self):
        """启用网络请求监听"""
        # 添加设置以启用Performance日志
        self.driver.execute_cdp_cmd("Network.enable", {})
        self.driver.execute_cdp_cmd("Performance.enable", {})
        
        logger.info("已启用网络请求监听")
    
    def get_network_logs(self):
        """获取网络请求日志并筛选出评论接口"""
        logs = self.driver.execute_cdp_cmd("Network.getResponseBody", {})
        return logs
    
    def login(self):
        """
        登录网站，支持手动扫码登录或者从物理机浏览器导入Cookie
        :return: 是否登录成功
        """
        try:
            if self.is_logged_in:
                logger.info("已处于登录状态")
                return True
            
            # 使用物理机浏览器的登录状态
            return True
            
        except Exception as e:
            logger.error(f"登录过程出现异常: {str(e)}")
            return False
    
    def scrape_comments(self, url):
        """抓取指定页面的评论信息"""
        self.url = url
        try:
            if not self.is_logged_in:
                logger.error("未登录状态，无法抓取数据")
                return None
            
            logger.info(f"开始抓取评论: {url}")
            self.driver.get(url)
            self.random_sleep(3, 5)  # 等待页面加载
            
            # 监听评论接口的网络请求
            self.capture_network_traffic(url)
            
            # 1. 点击评论按钮 - 根据提供的class
            try:
                logger.info("点击评论按钮...")
                comment_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".qSsCHWSU.GdNlylMd.u4mlHKc5"))
                )
                comment_button.click()
                self.random_sleep(2, 3)  # 等待评论抽屉加载
                logger.info("评论抽屉已打开")
            except Exception as e:
                logger.error(f"点击评论按钮出错: {str(e)}")
                return None
            
            # 2. 采用全新的递归式展开评论与滚动策略
            try:
                logger.info("开始加载评论，采用递归式展开策略...")
                
                # 查找评论容器
                possible_containers = [
                    ".HV3aiR5J.comment-mainContent.iV2CcAAV",
                ]
                
                container_element = None
                container_selector = None
                
                for selector in possible_containers:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements and len(elements) > 0:
                            container_element = elements[0]
                            container_selector = selector
                            logger.info(f"找到评论容器: {selector}")
                            break
                    except:
                        continue
                
                if not container_element:
                    logger.error("未找到评论容器，无法加载评论")
                    return None
                
                # 可能的展开回复按钮选择器
                possible_expand_selectors = [
                    ".jlqd8usT.comment-reply-expand-btn",
                ]
                
                # 点击过的按钮集合
                clicked_expand_buttons = set()
                
                # 记录总共点击的按钮数
                total_clicked_buttons = 0
                
                # 记录上次内容高度，用于判断是否有新内容加载
                last_content_height = 0
                no_new_content_count = 0
                
                # 最大循环次数，防止无限循环
                iteration_count = 0
                
                # 滚动到页面顶部开始处理
                self.driver.execute_script(f"document.querySelector('{container_selector}').scrollTop = 0;")
                self.random_sleep(1, 2)
                
                while True:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, 'fanRMYie')
                    if elements and len(elements) > 0:
                        break
                    iteration_count += 1
                    logger.info(f"======== 第 {iteration_count} 次迭代 ========")
                    
                    # # 获取当前内容高度
                    # current_content_height = self.driver.execute_script(
                    #     f"return document.querySelector('{container_selector}').scrollHeight;"
                    # )
                    # logger.info(f"当前内容高度: {current_content_height}, 上次内容高度: {last_content_height}")
                    #
                    # # 判断内容是否有变化
                    # has_new_content = current_content_height > last_content_height
                    # if has_new_content:
                    #     no_new_content_count = 0
                    # else:
                    #     no_new_content_count += 1
                    #
                    # # 如果连续3次没有新内容，结束循环
                    # if no_new_content_count >= 3:
                    #     logger.info(f"连续 {no_new_content_count} 次没有新内容加载，结束抓取")
                    #     break
                    
                    # 递归展开所有可见的"展开回复"按钮
                    # expand_count = self._recursive_expand_replies(container_selector, possible_expand_selectors, clicked_expand_buttons)
                    # logger.info(f"本次迭代共展开 {expand_count} 个回复")
                    # total_clicked_buttons += expand_count
                    
                    # 处理网络请求
                    self.process_network_requests()
                    
                    # 如果这次循环没有展开新按钮，则需要滚动加载更多内容
                    # if expand_count == 0:
                    #     # 滚动到底部加载更多评论
                    #     logger.info("没有找到新的展开按钮，滚动到底部加载更多评论")
                    #
                    #     self.random_sleep(2, 3)  # 等待新内容加载
                    #
                    #     # 处理网络请求
                    #     self.process_network_requests()
                    #
                    # # 更新上次内容高度
                    # last_content_height = current_content_height
                    self._scroll_to_bottom(container_selector)
                    # 检查是否有用户中断
                    if keyboard.is_pressed('ctrl+c'):
                        logger.info("检测到中断信号，停止抓取")
                        # break
                
                logger.info(f"评论抓取完成，共点击展开 {total_clicked_buttons} 个回复")
                return True
                
            except Exception as e:
                logger.error(f"抓取评论出错: {str(e)}")
                return None
            
        except Exception as e:
            logger.error(f"抓取评论出错: {str(e)}")
            return None
    
    def capture_network_traffic(self, url):
        """设置网络请求捕获"""
        # 注入JavaScript代码监听网络请求
        capture_script = """
        var originalXHROpen = XMLHttpRequest.prototype.open;
        var originalXHRSend = XMLHttpRequest.prototype.send;
        var requestData = {};

        XMLHttpRequest.prototype.open = function(method, url) {
            // 记录请求URL
            this._url = url;
            // 调用原始的open方法
            return originalXHROpen.apply(this, arguments);
        };

        XMLHttpRequest.prototype.send = function(data) {
            // 添加加载完成后的回调
            if (this._url && this._url.includes('/aweme/v1/web/comment/list/')) {
                var xhr = this;
                var loadListener = function() {
                    try {
                        var responseData = JSON.parse(xhr.responseText);
                        // 创建自定义事件并传递相关数据
                        var event = new CustomEvent('comment_api_response', {
                            detail: {
                                url: xhr._url,
                                data: responseData
                            }
                        });
                        document.dispatchEvent(event);
                    } catch (e) {
                        console.error('Failed to parse response', e);
                    }
                };
                
                this.addEventListener('load', loadListener);
            }
            
            // 调用原始的send方法
            return originalXHRSend.apply(this, arguments);
        };
        
        // 清除警告信息，若有
        console.clear();
        """
        
        # 执行JavaScript脚本
        self.driver.execute_script(capture_script)
        
        # 添加事件监听器，监听评论API响应
        listen_script = """
        document.addEventListener('comment_api_response', function(e) {
            // 将API响应数据存储为全局变量
            window.latestCommentResponse = e.detail;
            console.log('Captured comment API response:', e.detail.url);
        });
        """
        
        self.driver.execute_script(listen_script)
        logger.info("已启用评论API监听")
    
    def process_network_requests(self):
        """处理捕获的网络请求，提取并打印评论接口数据"""
        try:
            # 检查是否有捕获到的评论API响应
            has_response = self.driver.execute_script("return window.latestCommentResponse !== undefined")
            
            if has_response:
                # 获取评论API响应数据
                response_data = self.driver.execute_script("var data = window.latestCommentResponse; window.latestCommentResponse = undefined; return data;")
                
                if response_data and 'data' in response_data:
                    # 打印API URL
                    logger.info(f"捕获到评论API请求: {response_data['url']}")
                    
                    # 打印API响应数据
                    print("\n========== 评论API响应数据 ==========")
                    print(f"URL: {response_data['url']}")
                    comments = response_data['data']['comments']
                    for c in comments:
                        data = {
                            'cid': c['cid'],
                            'comment_text': c['text'],
                            'reply_id': c['reply_id'],
                            'reply_to_reply_id': c['reply_to_reply_id'],
                            'root_comment_id': c.get('root_comment_id', '0'),
                            'status': c['status'],
                            'level': c['level'],
                            'comment_reply_total': c.get('comment_reply_total', '0'),
                            'content_type': c.get('content_type', '0'),
                            'comment_create_time': c.get('create_time'),
                            'aweme_id': c.get('aweme_id', ''),
                            'note_id': c.get('aweme_id', ''),
                            'note_url': self.url,
                            'sync_last_time': datetime.now(),
                        }
                        self.db.save_comment(data)
        except Exception as e:
            logger.error(f"处理网络请求数据出错: {str(e)}")
    
    def _save_cookies(self):
        """保存Cookie到文件"""
        try:
            cookies = self.driver.get_cookies()
            with open(self.cookie_file, 'wb') as f:
                pickle.dump(cookies, f)
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
            
            # 先访问目标网站
            self.driver.get(self.base_url)
            
            with open(self.cookie_file, 'rb') as f:
                cookies = pickle.load(f)
            
            for cookie in cookies:
                # 处理可能缺少的cookie属性
                if 'expiry' in cookie:
                    cookie['expiry'] = int(cookie['expiry'])
                
                try:
                    self.driver.add_cookie(cookie)
                except:
                    continue
            
            # 刷新页面使Cookie生效
            self.driver.refresh()
            
            logger.info(f"已从 {self.cookie_file} 加载Cookie")
            return True
        except Exception as e:
            logger.error(f"加载Cookie出错: {str(e)}")
            return False
    
    def close(self):
        """关闭浏览器"""
        try:
            if hasattr(self, 'driver'):
                self.driver.quit()
            logger.info("浏览器已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器时出错: {str(e)}")
    
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
    
    def _recursive_expand_replies(self, container_selector, possible_expand_selectors, clicked_expand_buttons):
        """
        递归展开所有可见的回复按钮
        返回本次递归中点击的按钮数量
        """
        total_expand_count = 0
        has_new_expansion = True
        max_recursion_depth = 20  # 防止无限递归
        recursion_depth = 0
        
        # 继续递归直到没有新的展开按钮被点击
        while has_new_expansion and recursion_depth < max_recursion_depth:
            recursion_depth += 1
            logger.info(f"递归展开回复 - 第 {recursion_depth} 轮")
            
            # 找出当前可见的所有展开按钮并点击
            current_expand_count = 0
            
            # 遍历所有可能的选择器
            for expand_selector in possible_expand_selectors:
                try:
                    # 获取当前可见的所有展开按钮
                    visible_buttons = []
                    expand_buttons = self.driver.find_elements(By.CSS_SELECTOR, expand_selector)
                    
                    # 筛选出可见的按钮
                    for btn in expand_buttons:
                        try:
                            if btn.is_displayed():
                                visible_buttons.append(btn)
                        except:
                            continue
                    
                    logger.info(f"找到 {len(visible_buttons)} 个可见的展开按钮: {expand_selector}")
                    
                    # 依次点击每个未点击过的按钮
                    for i, btn in enumerate(visible_buttons):
                        try:
                            # 获取按钮唯一标识
                            btn_id = self.driver.execute_script("""
                                try {
                                    arguments[0].scrollIntoView({block: 'center'});
                                    const rect = arguments[0].getBoundingClientRect();
                                    return `${rect.x},${rect.y},${arguments[0].textContent.trim()}`;
                                } catch(e) {
                                    return null;
                                }
                            """, btn)
                            
                            # 如果按钮未点击过，则点击
                            if btn_id and btn_id not in clicked_expand_buttons:
                                # 确保按钮在视图中央
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                self.random_sleep(0.3, 0.5)
                                
                                logger.info(f"点击展开按钮: {btn_id}")
                                
                                # 尝试点击按钮
                                try:
                                    btn.click()
                                except:
                                    try:
                                        self.driver.execute_script("arguments[0].click();", btn)
                                    except:
                                        logger.error("点击按钮失败，跳过")
                                        continue
                                
                                # 标记为已点击
                                clicked_expand_buttons.add(btn_id)
                                current_expand_count += 1
                                total_expand_count += 1
                                
                                # 等待内容加载
                                self.random_sleep(1, 2)
                                
                                # 处理网络请求
                                self.process_network_requests()
                        except Exception as e:
                            logger.error(f"处理展开按钮出错: {str(e)}")
                            continue
                except Exception as e:
                    logger.error(f"查找展开按钮出错: {str(e)}")
                    continue
            
            # 如果本轮没有点击新按钮，结束递归
            logger.info(f"本轮共点击 {current_expand_count} 个展开按钮")
            has_new_expansion = current_expand_count > 0
        
        logger.info(f"递归展开完成，共点击 {total_expand_count} 个按钮")
        return total_expand_count
    
    def _scroll_to_bottom(self, container_selector):
        """
        平滑滚动到评论容器底部
        """
        try:
            # 获取当前滚动位置和容器高度
            current_scroll_position = self.driver.execute_script(
                f"return document.querySelector('{container_selector}').scrollTop;"
            )
            scroll_height = self.driver.execute_script(
                f"return document.querySelector('{container_selector}').scrollHeight;"
            )
            client_height = self.driver.execute_script(
                f"return document.querySelector('{container_selector}').clientHeight;"
            )
            
            # 计算需要滚动的总距离
            total_scroll_distance = scroll_height - current_scroll_position - client_height
            
            # 如果已经在底部，不需要滚动
            if total_scroll_distance <= 0:
                logger.info("已经在底部，无需滚动")
                return
            
            logger.info(f"开始平滑滚动到底部，总距离: {total_scroll_distance}")
            
            # 平滑滚动，每次滚动一小段距离
            steps = min(10, max(2, int(total_scroll_distance / 500)))  # 根据总距离确定步数，至少3步，最多10步
            scroll_step = total_scroll_distance / steps
            
            for i in range(steps):
                # 计算当前步的滚动距离
                step_distance = int(scroll_step * (i + 1))
                target_position = current_scroll_position + step_distance
                
                # 执行滚动
                self.driver.execute_script(
                    f"document.querySelector('{container_selector}').scrollTop = {target_position};"
                )
                
                # 等待一小段时间，模拟人工滚动
                # self.random_sleep(0.3, 0.7)
                
                # 处理网络请求
                self.process_network_requests()
            
            # 最后确保滚动到底部
            self.driver.execute_script(
                f"document.querySelector('{container_selector}').scrollTop = document.querySelector('{container_selector}').scrollHeight;"
            )
            
            logger.info("已滚动到底部")
            
        except Exception as e:
            logger.error(f"滚动到底部出错: {str(e)}")
            # 尝试直接跳转到底部
            try:
                self.driver.execute_script(
                    f"document.querySelector('{container_selector}').scrollTop = document.querySelector('{container_selector}').scrollHeight;"
                )
            except:
                pass
