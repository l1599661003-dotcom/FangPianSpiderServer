from sqlalchemy import Column, Integer, String, Numeric, DateTime, Text, TIMESTAMP, BigInteger, DECIMAL
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class TrainingBloggerDetails(Base):
    __tablename__ = 'training_blogger_details_1月大梦拆'

    id = Column(Integer, primary_key=True)
    account_id = Column(String(256))
    nickname = Column(Integer)
    blogger_dandelion_id = Column(String(300))
    followers_count = Column(String(300))
    organization_name = Column(Integer)
    graphic_price = Column(String(256))
    video_price = Column(String(256))
    current_note_count = Column(String(256))
    graphic_orders_count = Column(String(256))
    video_orders_count = Column(String(256))
    tags = Column(String(256))
    graphic_revenue = Column(String(256))
    video_revenue = Column(String(256))
    total_revenue = Column(String(256))
    page = Column(String(256))
    month = Column(String(256))
    is_updated = Column(String(256))
    intro = Column(String(256))
    type = Column(String(256))
    updated_at = Column(String(100))
    created_at = Column(String(100))


class KolMediaAccountsJianlian(Base):
    __tablename__ = 'kol_media_accounts_jianlian'

    id = Column(Integer, primary_key=True)
    nickname = Column(String(255))
    pgy_id = Column(String(50))
    contact_info = Column(String(255))
    monthly_income = Column(Integer)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)
    record_id = Column(String(50))

class FeiShuToken(Base):
    __tablename__ = 'feishu_tokens'

    id = Column(Integer, primary_key=True)
    token = Column(String(255))
    fetch_time = Column(DateTime)
    expire = Column(Integer)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)


class BoZhu(Base):
    __tablename__ = '博主'

    id = Column(Integer, primary_key=True)
    pgy_id = Column(String(255))

class JiGou(Base):
    __tablename__ = '机构'

    id = Column(Integer, primary_key=True)
    jigou = Column(String(255))

class PaiMing(Base):
    __tablename__ = '排名总'

    id = Column(Integer, primary_key=True)
    达人昵称 = Column(String(255))
    达人粉丝量 = Column(Integer)
    达人所属机构 = Column(String(255))
    标签 = Column(String(100))
    图文商单数量 = Column(Integer)
    视频商单数量 = Column(Integer)
    图文营收 = Column(Numeric(10, 2))
    视频营收 = Column(Numeric(10, 2))
    月总营收 = Column(Numeric(10, 2))
    博主id = Column(String(100))
    图文价格 = Column(Numeric(10, 2))
    视频价格 = Column(Numeric(10, 2))
    所属月份 = Column(String(255))
    小红书账号 = Column(String(255))
    简介 = Column(String(255))

class PaiMing25_1(Base):
    __tablename__ = '母婴'

    id = Column(Integer, primary_key=True)
    达人昵称 = Column(String(255))
    达人粉丝量 = Column(Integer)
    达人所属机构 = Column(String(255))
    标签 = Column(String(100))
    图文商单数量 = Column(Integer)
    视频商单数量 = Column(Integer)
    图文营收 = Column(Numeric(10, 2))
    视频营收 = Column(Numeric(10, 2))
    月总营收 = Column(Numeric(10, 2))
    博主id = Column(String(100))
    图文价格 = Column(Numeric(10, 2))
    视频价格 = Column(Numeric(10, 2))
    所属月份 = Column(String(255))
    小红书账号 = Column(String(255))
    简介 = Column(String(255))

class KolMediaAccountsWaicai(Base):
    __tablename__ = 'kol_media_accounts_waicai'

    id = Column(Integer, primary_key=True)
    nickname = Column(String(255))
    user_id = Column(Integer)
    pgy_id = Column(String(50))
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)
    delete_type = Column(Integer)
    status = Column(Integer)


class KolMediaAccountsWaicaiInfo(Base):
    __tablename__ = 'kol_media_accounts_waicai_info'

    id = Column(Integer, primary_key=True, autoincrement=True)
    is_update = Column(Integer)
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
    daily_pic_video_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0,
                                              comment='日常图文+视频百赞笔记比例')
    daily_pic_video_hundred_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0,
                                                      comment='日常图文+视频千赞笔记比例')
    daily_pic_video_completion_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文+视频完播率')
    daily_pic_video_three_sec_reading_rate = Column(DECIMAL(10, 4), nullable=False, default=0,
                                                    comment='日常图文+视频图文3秒阅读率')

    # 合作图文+视频相关字段
    cooperation_pic_video_exposure_median = Column(Integer, nullable=False, default=0,
                                                   comment='合作图文+视频曝光中位数')
    cooperation_pic_video_reading_median = Column(Integer, nullable=False, default=0, comment='合作图文+视频阅读中位数')
    cooperation_pic_video_interaction_median = Column(Integer, nullable=False, default=0,
                                                      comment='合作图文+视频互动中位数')
    cooperation_pic_video_interaction_rate = Column(DECIMAL(10, 4), nullable=False, default=0,
                                                    comment='合作图文+视频互动率')
    cooperation_pic_video_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0,
                                                    comment='合作图文+视频百赞笔记比例')
    cooperation_pic_video_hundred_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0,
                                                            comment='合作图文+视频千赞笔记比例')
    cooperation_pic_video_completion_rate = Column(DECIMAL(10, 4), nullable=False, default=0,
                                                   comment='合作图文+视频完播率')
    cooperation_pic_video_three_sec_reading_rate = Column(DECIMAL(10, 4), nullable=False, default=0,
                                                          comment='合作图文+视频图文3秒阅读率')

    # 日常图文相关字段
    daily_pic_text_exposure_median = Column(Integer, nullable=False, default=0, comment='日常图文曝光中位数')
    daily_pic_text_reading_median = Column(Integer, nullable=False, default=0, comment='日常图文阅读中位数')
    daily_pic_text_interaction_median = Column(Integer, nullable=False, default=0, comment='日常图文互动中位数')
    daily_pic_text_interaction_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文互动率')
    daily_pic_text_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文百赞笔记比例')
    daily_pic_text_hundred_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0,
                                                     comment='日常图文千赞笔记比例')
    daily_pic_text_completion_rate = Column(DECIMAL(10, 4), nullable=False, default=0, comment='日常图文完播率')
    daily_pic_text_three_sec_reading_rate = Column(DECIMAL(10, 4), nullable=False, default=0,
                                                   comment='日常图文3秒阅读率')
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
    daily_video_hundred_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0,
                                                  comment='日常视频百赞笔记比例')
    daily_video_thousand_likes_note_ratio = Column(DECIMAL(10, 4), nullable=False, default=0,
                                                   comment='日常视频千赞笔记比例')
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

    followers_increase = Column(DECIMAL(5, 2), nullable=False, default=0, comment='粉丝增量')
    followers_change_rate = Column(DECIMAL(5, 2), nullable=False, default=0, comment='粉丝量变化幅度')

class BusinessContractPhone(Base):
    __tablename__ = 'business_contract_phone'

    id = Column(Integer, primary_key=True)
    nickname = Column(String(255))
    xiaohongshu_url = Column(String(255))
    contract_person = Column(String(255))
    contract_person_feishu = Column(String(255))
    contract_person_img = Column(String(255))
    contract_person_name = Column(String(255))
    train_person_feishu = Column(String(255))
    train_person_img = Column(String(255))
    train_person_name = Column(String(255))
    contract_person_group = Column(String(255))
    contract_person_phone = Column(String(255))
    teacher = Column(String(255))
    teacher_phone = Column(String(255))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class FrontTow(Base):
    __tablename__ = 'front_tow'

    id = Column(Integer, primary_key=True)
    机构名称 = Column(String(255))
    业务模式 = Column(String(255))

class XiaohongshuComment(Base):
    __tablename__ = 'xiaohongshu_comment'

    id = Column(Integer, primary_key=True)
    comment_content = Column(Text)
    comment_id = Column(String(255))
    comment_time = Column(String(255))
    # reply_content = Column(String(255))
    # reply_id = Column(String(255))
    # reply_time = Column(String(255))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class SpiderQianguaHotNote(Base):
    __tablename__ = 'spider_qiangua_hot_note'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='ID')
    kol_name = Column(String(128), comment='博主名称')
    note_title = Column(String(128), comment='笔记标题')
    xiaohongshu_user_id = Column(String(32), comment='博主user_id')
    xiaohongshu_note_id = Column(String(32), comment='笔记小红书id')
    kol_img = Column(String(128), comment='博主头像')
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
    note_tags = Column(String(255), comment='笔记标签')
    note_tag_classify = Column(String(128), comment='笔记标签分类')
    hot_note_24h = Column(String(128), comment='排名时间（近24小时）')
    note_type = Column(Integer, comment='笔记类型')
    hot_date = Column(Integer, comment='日期0点时间戳')
    create_time = Column(Integer, unsigned=True, comment='创建时间')
    update_time = Column(Integer, unsigned=True, comment='更新时间')