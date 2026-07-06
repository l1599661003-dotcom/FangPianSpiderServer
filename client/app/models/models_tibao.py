from datetime import datetime
import time

from sqlalchemy import Column, Integer, String, TIMESTAMP, DateTime, Numeric, Text, Boolean, Float, BigInteger, ForeignKey, DECIMAL
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Setting(Base):
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    name = Column(String(256))
    key = Column(String(256))
    value = Column(String(256))
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)

class XiaohongshuMonth(Base):
    __tablename__ = 'xiaohongshu_month'

    id = Column(Integer, primary_key=True)
    xiaohongshu_url = Column(String(255))
    data = Column(String(255))
    status = Column(Integer)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class ChinaProvince(Base):
    __tablename__ = 'china_province'

    id = Column(Integer, primary_key=True)
    province_name = Column(String(25))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class ChinaCity(Base):
    __tablename__ = 'china_city'

    id = Column(Integer, primary_key=True)
    province_name = Column(String(25))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class KolMediaAccount(Base):
    __tablename__ = 'kol_media_accounts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    nickname = Column(String(255), nullable=False, comment='博主昵称')
    xhs_url = Column(Text, comment='小红书链接')
    followers = Column(Integer, comment='粉丝数量')
    like_count = Column(Integer, comment='赞藏数量')
    phone = Column(String(255), comment='电话')
    wechat = Column(String(255), comment='微信')
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)
    sign_type = Column(String(255), comment='签约类型，自孵化或签约')
    is_enable = Column(Integer, default=1, nullable=False, comment='签约状态，0：解约，1：签约，2：可回签')
    revenue_percent = Column(Numeric(8, 2), default=0.80)
    profit_type = Column(String(20))
    fixed_price = Column(Numeric(8, 2), nullable=False, default=0.00, comment='一口价')
    fixed_price_1_1 = Column(Numeric(8, 2), default=0.00)
    fixed_price_1_2 = Column(Numeric(8, 2), default=0.00)
    fixed_price_1_3 = Column(Numeric(8, 2), default=0.00)
    fixed_price_2_4 = Column(Numeric(8, 2), default=0.00)
    fixed_price_2_5 = Column(Numeric(8, 2), default=0.00)
    fixed_price_2_6 = Column(Numeric(8, 2), default=0.00)
    referrer = Column(String(255), comment='推荐人，手动输入')
    referrer_shangwu = Column(Integer, default=0)
    account_level = Column(String(200), comment='账号等级')
    username = Column(String(255), comment='姓名')
    id_card = Column(String(255), comment='身份证')
    bank_card = Column(String(255), comment='银行卡号')
    tags = Column(String(255), comment='账号标签')
    talent_id = Column(String(100), comment='达人ID')
    privileged_time = Column(String(200), comment='授权时间')
    child_age = Column(Numeric(3, 1), comment='母婴孩子年龄')
    child_sex = Column(String(200), comment='母婴孩子性别：1=男，2=女')
    pet_supplies = Column(String(255), comment='宠物品种')
    pet_age = Column(String(200), comment='宠物年龄')
    fixed_price_proportion = Column(Numeric(8, 5), nullable=False, default=0.00000, comment='一口价分成比例')
    address = Column(String(255), comment='小红书地址（省市区类型）')
    groups = Column(Integer, comment='分组')
    refund_ratio = Column(Numeric(3, 2), comment='返点比例')
    refund_ratio_fei = Column(Numeric(5, 2), comment='非年框返点比例')

    # 数据指标
    daily_video_exposure_median = Column(Numeric(10, 2), comment='日常视频曝光中位数')
    daily_video_reading_median = Column(Numeric(10, 2), comment='日常视频阅读中位数')
    daily_video_interaction_median = Column(Numeric(10, 2), comment='日常视频互动中位数')
    daily_video_interaction_rate = Column(Numeric(10, 4), comment='日常视频互动率')
    
    # 用户画像数据
    age_less_than_18 = Column(Numeric(5, 2), nullable=False, default=0.00, comment='年龄<18')
    age_18_to_24 = Column(Numeric(5, 2), nullable=False, default=0.00, comment='年龄18_24')
    age_25_to_34 = Column(Numeric(5, 2), nullable=False, default=0.00, comment='年龄25_34')
    age_35_to_44 = Column(Numeric(5, 2), nullable=False, default=0.00, comment='年龄35_44')
    age_greater_than_44 = Column(Numeric(5, 2), nullable=False, default=0.00, comment='年龄>44')
    male_fan_percentage = Column(Numeric(5, 2), nullable=False, default=0.00, comment='男粉丝占比')
    female_fan_percentage = Column(Numeric(5, 2), nullable=False, default=0.00, comment='女粉丝占比')

    # 兴趣和地域数据
    interest_top1 = Column(String(255), comment='用户兴趣top1')
    interest_top2 = Column(String(255), comment='用户兴趣top2')
    interest_top3 = Column(String(255), comment='用户兴趣top3')
    interest_top4 = Column(String(255), comment='用户兴趣top4')
    interest_top5 = Column(String(255), comment='用户兴趣top5')
    province_top1 = Column(String(255), comment='省份top1')
    province_top2 = Column(String(255), comment='省份top2')
    province_top3 = Column(String(255), comment='省份top3')
    city_top1 = Column(String(255), comment='城市top1')
    city_top2 = Column(String(255), comment='城市top2')
    city_top3 = Column(String(255), comment='城市top3')
    device_top1 = Column(String(255), comment='设备top1')
    device_top2 = Column(String(255), comment='设备top2')
    device_top3 = Column(String(255), comment='设备top3')

    # 笔记和合作数据
    notes_published = Column(Integer, nullable=False, default=0, comment='发布笔记数量')
    content_categories = Column(String(200), comment='内容类目及占比')
    cooperated_industries = Column(String(255), comment='合作行业')
    
    # 平台相关数据
    dandelion_platform_link = Column(String(255), comment='蒲公英平台链接')
    dandelion_platform_id = Column(String(255), comment='蒲公英平台ID')
    graphic_price = Column(Numeric(10, 2), comment='图文一口价')
    video_price = Column(Numeric(10, 2), comment='视频一口价')
    
    # 其他业务数据
    shipping_address = Column(String(200), comment='所在地区')
    blogger_rebate_ratio = Column(Numeric(5, 2), nullable=False, default=0.20, comment='博主返点比例')
    dw_id = Column(String(255), comment='多维表格id')
    record_id = Column(String(255), comment='多维表格record')
    
    # 系统统计数据
    system_total_orders = Column(Integer, nullable=False, default=0, comment='系统总商单量')
    system_orders_30_days = Column(Integer, nullable=False, default=0, comment='系统30天商单量')
    system_orders_90_days = Column(Integer, nullable=False, default=0, comment='系统90天商单量')
    pgy_total_orders = Column(Integer, nullable=False, default=0, comment='蒲公英总商单量')
    pgy_orders_30_days = Column(Integer, nullable=False, default=0, comment='蒲公英30天商单量')
    pgy_orders_90_days = Column(Integer, nullable=False, default=0, comment='蒲公英90天商单量')
    
    # 状态标记
    is_update = Column(Integer, nullable=False, default=1, comment='当天是否更新')
    currentLevel = Column(Integer, default=2, comment='当前等级')
    is_water_account = Column(Integer, default=0, comment='是否是水号 0否 1是')
    is_added_to_training_group = Column(Integer, nullable=False, default=0, comment='是否拉培训群')
    is_added_to_operation_group = Column(Integer, nullable=False, default=0, comment='是否拉运营群')

    # 阅读数据
    read_median = Column(Integer, nullable=False, default=0, comment='阅读中位数')
    interaction_median = Column(Integer, nullable=False, default=0, comment='互动中位数')
    coop_pic_text_exposure_median = Column(Integer, nullable=False, default=0, comment='互动中位数')
    # imp_median = Column(Integer, comment='图文+视频曝光中位数')

    # 添加缺失的字段
    picture_read_cost = Column(DECIMAL(10, 2), nullable=True, default=0, comment='图文阅读单价')
    video_read_cost = Column(DECIMAL(10, 2), nullable=True, default=0, comment='视频阅读单价')
    gender = Column(String(10), nullable=True, comment='性别')
    reading_followers_percentage = Column(DECIMAL(10, 4), nullable=True, default=0, comment='阅读粉丝占比')
    engaged_followers_percentage = Column(DECIMAL(10, 4), nullable=True, default=0, comment='互动粉丝占比')
    reading_followers_benchmark_exceed = Column(DECIMAL(10, 4), nullable=True, default=0, comment='阅读粉丝基准超出')
    engaged_followers_benchmark_exceed = Column(DECIMAL(10, 4), nullable=True, default=0, comment='互动粉丝基准超出')
    brand_name = Column(Text, nullable=True, comment='品牌名称')
    active_followers_percentage = Column(DECIMAL(10, 4), nullable=True, default=0, comment='活跃粉丝占比')
    active_followers_benchmark_exceed = Column(DECIMAL(10, 4), nullable=True, default=0, comment='活跃粉丝基准超出')
    notesign = Column(String(255), nullable=True, comment='博主所在机构')
    last_update_time = Column(DateTime, nullable=True, comment='最后更新时间')

    # 日常图文+视频相关字段
    daily_pic_video_exposure_median = Column(Integer, nullable=False, default=0, comment='日常图文+视频曝光中位数')
    daily_pic_video_reading_median = Column(Integer, nullable=False, default=0, comment='日常图文+视频阅读中位数')
    daily_pic_video_interaction_median = Column(Integer, nullable=False, default=0, comment='日常图文+视频互动中位数')
    daily_pic_video_interaction_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文+视频互动率')
    daily_pic_video_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文+视频百赞笔记比例')
    daily_pic_video_hundred_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文+视频千赞笔记比例')
    daily_pic_video_completion_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文+视频完播率')
    daily_pic_video_three_sec_reading_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文+视频图文3秒阅读率')

    # 合作图文+视频相关字段
    cooperation_pic_video_exposure_median = Column(Integer, nullable=False, default=0, comment='合作图文+视频曝光中位数')
    cooperation_pic_video_reading_median = Column(Integer, nullable=False, default=0, comment='合作图文+视频阅读中位数')
    cooperation_pic_video_interaction_median = Column(Integer, nullable=False, default=0, comment='合作图文+视频互动中位数')
    cooperation_pic_video_interaction_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='合作图文+视频互动率')
    cooperation_pic_video_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0, comment='合作图文+视频百赞笔记比例')
    cooperation_pic_video_hundred_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0, comment='合作图文+视频千赞笔记比例')
    cooperation_pic_video_completion_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='合作图文+视频完播率')
    cooperation_pic_video_three_sec_reading_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='合作图文+视频图文3秒阅读率')

    # 日常图文相关字段
    daily_pic_text_exposure_median = Column(Integer, nullable=False, default=0, comment='日常图文曝光中位数')
    daily_pic_text_reading_median = Column(Integer, nullable=False, default=0, comment='日常图文阅读中位数')
    daily_pic_text_interaction_median = Column(Integer, nullable=False, default=0, comment='日常图文互动中位数')
    daily_pic_text_interaction_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文互动率')
    daily_pic_text_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文百赞笔记比例')
    daily_pic_text_hundred_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文千赞笔记比例')
    daily_pic_text_completion_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文完播率')
    daily_pic_text_three_sec_reading_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文3秒阅读率')
    daily_pic_text_notenumber = Column(Integer, nullable=False, default=0, comment='日常图文笔记数')

    # CPE、CPM、CPC、CPR相关字段
    daily_pic_text_cpe = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常图文CPE')
    daily_pic_text_cpm = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常图文CPM')
    daily_pic_text_cpc = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常图文CPC')
    daily_pic_text_cpr = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常图文CPR')

    # 合作图文相关字段
    coop_pic_text_cpe = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作图文CPE')
    coop_pic_text_cpm = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作图文CPM')
    coop_pic_text_cpc = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作图文CPC')
    coop_pic_text_cpr = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作图文CPR')

    # 合作图文视频相关字段
    cooperation_pic_video_video_cpe = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作视频CPE')
    cooperation_pic_video_video_cpc = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作视频CPC')
    cooperation_pic_video_video_cpm = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作视频CPM')
    cooperation_pic_video_video_cpr = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作视频CPR')
    cooperation_pic_video_text_cpe = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作图文CPE')
    cooperation_pic_video_text_cpc = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作图文CPC')
    cooperation_pic_video_text_cpm = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作图文CPM')
    cooperation_pic_video_text_cpr = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作图文CPR')

    # 日常视频相关字段
    daily_video_hundred_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常视频百赞笔记比例')
    daily_video_thousand_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常视频千赞笔记比例')
    daily_video_three_sec_reading_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常视频3秒阅读率')
    daily_video_notenumber = Column(Integer, nullable=False, default=0, comment='日常视频笔记数')
    daily_video_completion_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常视频完播率')

    # 日常图文视频文本相关字段
    daily_pic_video_text_cpe = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常图文视频文本CPE')
    daily_pic_video_text_cpc = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常图文视频文本CPC')
    daily_pic_video_text_cpm = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常图文视频文本CPM')
    daily_pic_video_text_cpr = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常图文视频文本CPR')

    # 日常视频成本指标
    daily_video_cpe = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常视频CPE')
    daily_video_cpc = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常视频CPC')
    daily_video_cpm = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常视频CPM')
    daily_video_cpr = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常视频CPR')

    # 合作视频成本指标
    coop_video_cpe = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作视频CPE')
    coop_video_cpc = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作视频CPC')
    coop_video_cpm = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作视频CPM')
    coop_video_cpr = Column(DECIMAL(10, 2), nullable=False, default=0, comment='合作视频CPR')

    # 日常图文视频成本指标
    daily_pic_video_video_cpe = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常图文视频CPE')
    daily_pic_video_video_cpc = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常图文视频CPC')
    daily_pic_video_video_cpm = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常图文视频CPM')
    daily_pic_video_video_cpr = Column(DECIMAL(10, 2), nullable=False, default=0, comment='日常图文视频CPR')

class AdminUserGroup(Base):
    """管理员用户组表"""
    __tablename__ = 'admin_user_groups'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, comment='分组名')
    p_id = Column(Integer, nullable=False, default=0, comment='父级分类')
    proportion = Column(Numeric(5, 2), nullable=False, default=-1.00, comment='分成比例')
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    level = Column(Integer, nullable=True, comment='用户组层级')

class AdminUser(Base):
    """管理员用户表"""
    __tablename__ = 'admin_users'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment='用户名')
    username = Column(String(255), nullable=False, comment='用户名')
    phone = Column(String(255), nullable=False, comment='手机号')
    avatar = Column(String(255), nullable=False, comment='头像')
    # email = Column(String(255), nullable=False, unique=True, comment='邮箱')
    password = Column(String(255), nullable=False, comment='密码')
    group = Column(Integer, nullable=True, comment='用户组')
    pm_group = Column(Integer, nullable=True, comment='PM组')
    remember_token = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    status = Column(Integer, default=1, comment='状态 1:启用 0:禁用')

class KolBusinessMediaAccount(Base):
    """KOL商务媒体账号表"""
    __tablename__ = 'kol_business_media_accounts'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    media_account_id = Column(BigInteger, nullable=False, comment='小红书账号')
    business_id = Column(BigInteger, nullable=False, comment='商务')
    director_id = Column(BigInteger, nullable=False, comment='编导')
    lead_director_id = Column(BigInteger, nullable=True, comment='主编/签约人')
    deputy_director_id = Column(BigInteger, nullable=True, comment='副管理人ID')
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    editor = Column(Integer, nullable=True, comment='剪辑')
    talent_id = Column(Integer, nullable=True)
    is_valid_business = Column(Integer, default=0, comment='是否离职：0-非离职，1-离职')

class BloggerSigningHistory(Base):
    """博主签约历史记录表"""
    __tablename__ = 'blogger_signing_and_cancellation_history'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    creator_id = Column(BigInteger, nullable=False, comment='博主ID')
    operator_id = Column(BigInteger, nullable=True, comment='操作人ID')
    action_time = Column(DateTime, nullable=False, default=datetime.now, comment='操作时间')
    status = Column(Integer, nullable=False, comment='状态 1:签约 0:解约')
    group = Column(Integer, nullable=True, comment='组别')
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

class KolOrder(Base):
    __tablename__ = 'kol_orders'
    
    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 基本信息
    record_id_no = Column(String(255), comment='飞书记录ID')
    no = Column(String(255), unique=True, nullable=False)
    sub_id = Column(Integer, nullable=False, default=0)
    admin_user_id = Column(Integer, nullable=False)
    director_id = Column(Integer, nullable=False)
    media_account_id = Column(Integer, nullable=False)
    
    # 订单信息
    brand = Column(String(255))
    category = Column(String(255), nullable=False)
    type = Column(String(255), nullable=False, comment='合作形式')
    price = Column(Integer, nullable=False)
    rebate_price = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    final_price = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    source = Column(String(255))
    stage = Column(Integer, nullable=False, default=0)
    
    # 时间相关
    closed_at = Column(DateTime)
    published_at = Column(DateTime)
    canceled_at = Column(DateTime)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # 取消原因和快递信息
    cancel_reason = Column(String(255))
    express_no = Column(String(255), comment='快递单号')
    
    # 创建者信息
    shangwu_creator = Column(Integer)
    director_creator = Column(Integer)
    talent_creator = Column(Integer, nullable=False, default=0)
    editor_creator = Column(Integer, nullable=False, default=0)
    
    # 联系信息
    wechat = Column(String(255))
    location = Column(String(255))
    company = Column(String(255))
    contacts = Column(String(255))
    contact_nickname = Column(String(255))
    
    # 发布相关
    pre_schedule = Column(DateTime)
    likes = Column(Integer, nullable=False, default=0)
    is_valid = Column(Integer, nullable=False, default=0)
    image = Column(String(255))
    publish_talent = Column(Integer, default=0)
    publish_editor = Column(Integer, default=0)
    publish_director = Column(Integer)
    publish_expired_time = Column(DateTime)
    published_data_time = Column(DateTime)
    
    # 财务相关
    input = Column(DECIMAL(10, 2), nullable=False, default=0.00, comment='投流金额')
    cost = Column(DECIMAL(10, 2), nullable=False, default=0.00, comment='制作成本')
    profit = Column(DECIMAL(10, 2), nullable=False, default=0.00, comment='利润')
    is_rebate = Column(Integer, nullable=False, default=0)
    is_finalized = Column(Integer, nullable=False, default=0)
    
    # 主管相关
    lead_director_creator = Column(Integer, nullable=False, default=0)
    lead_director_id = Column(Integer, nullable=False, default=0)
    company_id = Column(Integer)
    
    # 返点和溢价
    rebate_rate = Column(DECIMAL(20, 4), nullable=False, default=0.0000)
    rebate_rate_new = Column(DECIMAL(5, 2), comment='年框返点比例')
    premium_price = Column(DECIMAL(20, 4), nullable=False, default=0.0000, comment='溢价')
    
    # 文章和平台
    article_url = Column(String(1024))
    platform_id = Column(Integer, nullable=False, default=1)
    
    # 利润相关
    company_profit = Column(DECIMAL(20, 4), nullable=False, default=0.0000)
    contracted_profit = Column(DECIMAL(20, 4), nullable=False, default=0.0000)
    brand_id = Column(Integer, nullable=False, default=0)
    
    # 其他状态
    valid_time = Column(DateTime)
    deputy_director_id = Column(Integer)
    is_timeout = Column(Integer, nullable=False, default=0)
    remark = Column(String(255))
    lock_profit_fields = Column(Boolean, nullable=False, default=False)
    
    # 小红书相关
    red_book_order = Column(String(100), comment='小红书订单号')
    
    # 商务助理相关
    business_assistant_create = Column(Integer, comment='商务助理')
    business_assistant_jiekuan = Column(Integer, comment='商务助理')
    
    # 金额相关
    total_price = Column(DECIMAL(10, 2), nullable=False, default=0.00, comment='累计金额')
    
    # 年框相关
    year_frame_type_id = Column(Integer, nullable=False, default=0, comment='年框类型主键id字段')
    year_frame_type = Column(Integer, nullable=False, default=0, comment='年框类型字段')
    
    # 商务提成相关
    shangwu_rate = Column(DECIMAL(10, 2), comment='商务提成比例')
    shangwu_commission_rate = Column(DECIMAL(10, 2), comment='商务提成发放比例')
    shangwu_due_commission = Column(DECIMAL(10, 2), comment='商务应发提成')
    shangwu_paid_commission = Column(DECIMAL(10, 2), comment='商务实发提成')
    
    # 备注相关
    cw_remark = Column(Text, comment='财务备注')
    rebate_amount = Column(Text, comment='实际返点金额')
    
    # 分组相关
    xiaohongshu_account_group = Column(String(255), comment='小红书账号分组')
    completed_business_group = Column(String(255), comment='成单商务分组')
    settlement_business_group = Column(String(255), comment='结款商务分组')
    completed_assistant_group = Column(String(255), comment='成单商务助理分组')
    settlement_assistant_group = Column(String(255), comment='结款商务助理分组')
    
    # 是否打包相关
    dabao = Column(String(255), nullable=False, default='非打包', comment='是否打包')
    is_first = Column(String(255), nullable=False, default='否', comment='是否是首单')
    packaging_amount = Column(DECIMAL(8, 2), nullable=False, default=0.00, comment='打包累计金额')
    
    # 新增字段
    is_zero_price_declaration = Column(Boolean, nullable=False, default=False, comment='是否是0元报备 1:是 0：否')
    redskins_planner_type = Column(String(255), comment='红人计划类型')
    redskins_planner_rate = Column(String(255), comment='红人计划比率')
    redskins_planner_money = Column(String(255), comment='红人计划金额')
    redskins_planner_accruing_amounts = Column(DECIMAL(15, 2), comment='红人计划累计金额')
    
    # 补发相关
    assistant_reissue_commission = Column(DECIMAL(10, 2), comment='表助理补发提成金额')
    settlement_assistant_reissue_commission = Column(DECIMAL(10, 2), comment='结款助理补发提成金额')
    reissue_amount = Column(DECIMAL(10, 2), comment='补发金额')
    
    # 其他
    notesign = Column(String(255), comment='博主所在机构')
    record_id = Column(String(50), nullable=False, default='', comment='飞书记录ID')
    gross_profit_margin = Column(DECIMAL(8, 2), nullable=False, default=0.00, comment='毛利润率')
    ticheng_updates = Column(Integer, nullable=False, default=0, comment='是否已更新商务提成 1-是 2-否')
    ticheng_updated_at = Column(DateTime, comment='商务提成更新时间')
    relation_id = Column(String(255), comment='关联ID')
    history_rebate_rate = Column(DECIMAL(8, 2), comment='历史返点比例')

    def __repr__(self):
        return f"<KolOrder(id={self.id}, no='{self.no}')>"

class TrainingBloggerDetails(Base):
    __tablename__ = 'training_blogger_details'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(String(244), nullable=True)  # 小红书ID
    nickname = Column(String(255), nullable=True)  # 昵称
    blogger_dandelion_id = Column(String(100), nullable=False)  # 荷公英ID
    followers_count = Column(Integer, nullable=False, default=0)  # 粉丝量
    organization_name = Column(String(255), nullable=True)  # 机构名称
    graphic_price = Column(DECIMAL(20, 4), nullable=False, default=0.0000)  # 图文报价
    video_price = Column(DECIMAL(20, 4), nullable=False, default=0.0000)  # 视频报价
    current_note_count = Column(Integer, nullable=False, default=0)  # 当前笔记总数
    graphic_orders_count = Column(Integer, nullable=False, default=0)  # 图文商单数量
    video_orders_count = Column(Integer, nullable=False, default=0)  # 视频商单数量
    tags = Column(String(255), nullable=True)  # 标签
    graphic_revenue = Column(DECIMAL(20, 4), nullable=False, default=0.0000)  # 图文总营收
    video_revenue = Column(DECIMAL(20, 4), nullable=False, default=0.0000)  # 视频总营收
    total_revenue = Column(DECIMAL(20, 4), nullable=False, default=0.0000)  # 总营收
    page = Column(Integer, nullable=True)  # 页数
    month = Column(String(7), nullable=True)  # 月份（格式如2024-06）
    created_at = Column(TIMESTAMP, nullable=False)  # 创建时间
    updated_at = Column(TIMESTAMP, nullable=False)  # 更新时间
    is_updated = Column(Integer, nullable=False, default=0)  # 是否更新
    intro = Column(Text, nullable=True)  # 简介
    type = Column(Integer, nullable=False, default=0)  # 1=图文2000-5000, 2=图文5001+, 3=视频2000-5000, 4=视频5001+

class SpiderQianguaHotNote(Base):
    __tablename__ = 'fp_spider_qiangua_hot_note'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='ID')
    kol_name = Column(String(128), comment='博主名称')
    note_title = Column(String(128), comment='笔记标题')
    xiaohongshu_user_id = Column(String(32), comment='博主user_id')
    xiaohongshu_note_id = Column(String(32), comment='笔记小红书id')
    xsec_token = Column(String(256), comment='笔记token')
    kol_img = Column(String(128), comment='博主头像')
    kol_image_id = Column(String(128), comment='博主头像id')
    kol_type = Column(String(128), comment='博主类型')
    note_like = Column(BigInteger, comment='点赞')
    note_collect = Column(BigInteger, comment='收藏')
    note_issue_time = Column(String(128), comment='笔记发布时间')
    note_comment = Column(BigInteger, comment='评论')
    note_share = Column(BigInteger, comment='分享')
    note_read = Column(BigInteger, comment='预估阅读')
    note_interact = Column(BigInteger, comment='互动量')
    note_classify = Column(String(128), comment='笔记分类')
    note_image = Column(String(255), comment='笔记封面')
    note_image_id = Column(String(255), comment='笔记封面id')
    note_tags = Column(String(255), comment='笔记标签')
    note_tag_classify = Column(String(128), comment='笔记标签分类')
    hot_note_24h = Column(String(128), comment='排名时间（近24小时）')
    note_type = Column(Integer, comment='笔记类型')
    hot_date = Column(Integer, comment='日期0点时间戳')
    create_time = Column(Integer, comment='创建时间')
    update_time = Column(Integer, comment='更新时间')

class DouYinAuthorInfo(Base):
    __tablename__ = 'douyin_author_info'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(32), unique=True, nullable=False, comment='抖音用户ID')
    user_name = Column(String(255), comment='用户名称')
    user_head_logo = Column(String(512), comment='用户头像')
    user_gender = Column(String(10), comment='用户性别')
    user_location = Column(String(255), comment='用户地址')
    user_introduction = Column(Text, comment='用户简介')
    fans_count = Column(BigInteger, comment='粉丝数')
    like_count = Column(BigInteger, comment='获赞数')
    item_count = Column(Integer, comment='作品数')
    first_tag_name = Column(String(255), comment='一级标签')
    second_tag_name = Column(String(255), comment='二级标签')
    user_aweme_url = Column(String(512), comment='抖音主页链接')
    profile_url = Column(String(512), comment='巨量算数主页链接')
    create_time = Column(DateTime, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

class DouYinVideoInfo(Base):
    __tablename__ = 'douyin_video_info'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(32), nullable=False, comment='抖音用户ID')
    picture = Column(String(512), comment='视频封面')
    video_text = Column(Text, comment='视频文案')
    like_cnt = Column(BigInteger, comment='点赞数')
    coment_cnt = Column(BigInteger, comment='评论数')
    share_cnt = Column(BigInteger, comment='分享数')
    follow_cnt = Column(BigInteger, comment='关注数')
    video_url = Column(String(512), comment='视频链接')
    rank = Column(Integer, comment='排名')
    item_id = Column(String(32), unique=True, comment='视频ID')
    create_time = Column(DateTime, comment='视频发布时间')
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

