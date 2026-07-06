from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Double, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression

from server.app.db.database import Base


# 爬虫客户端实体类
class FpSpiderClientModel(Base):
    """爬虫客户端模型
    
    用于存储爬虫客户端的基本信息，包括设备标识、状态等
    """
    __tablename__ = "fp_spider_client"  # 表名

    # 字段属性配置
    id = Column(Integer, primary_key=True, autoincrement=True, index=True, comment="主键ID")
    client_name = Column(String(50), nullable=False, index=True, comment="客户端名称")
    device_id = Column(String(64), unique=True, index=True, comment="设备唯一标识")
    ip_address = Column(String(39), comment="IP地址")  # IPv6最长39字符
    admin_id = Column(Integer, ForeignKey("user.id"), nullable=False, comment="管理员ID")
    admin = relationship("User", back_populates="spider_clients")
    status = Column(Integer, nullable=False, default=1, comment="状态：0-禁用，1-启用")
    is_online = Column(Boolean, nullable=False, server_default=expression.false(), comment="在线状态")
    create_time = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    update_time = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    client_tasks = relationship("FpSpiderClientTaskModel", back_populates="client", cascade="all, delete-orphan")

# 爬虫任务实体类
class FpSpiderTaskModel(Base):
    """爬虫任务模型
    
    用于存储爬虫任务的基本信息，包括任务类型、状态等
    """
    __tablename__ = "fp_spider_task"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True, comment="主键ID")
    spider_task_title = Column(String(128), nullable=False, index=True, comment="任务标题")
    task_type = Column(Integer, nullable=False, comment="任务类型：1-普通任务，2-定时任务")
    status = Column(Integer, nullable=False, default=0, comment="任务状态：0-待执行，1-执行中，2-已完成，3-已失败")
    start_time = Column(DateTime, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    head_users = Column(Integer, default=0, comment="头部用户数量")
    client_tasks = relationship("FpSpiderClientTaskModel", back_populates="task", cascade="all, delete-orphan")

# 爬虫客户端任务关联表
class FpSpiderClientTaskModel(Base):
    """爬虫客户端任务关联模型
    
    用于关联爬虫客户端和任务，记录任务执行状态
    """
    __tablename__ = "fp_spider_client_task"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True, comment="主键ID")
    client_id = Column(Integer, ForeignKey("fp_spider_client.id"), nullable=False, index=True, comment="客户端ID")
    task_id = Column(Integer, ForeignKey("fp_spider_task.id"), nullable=False, index=True, comment="任务ID")
    client = relationship("FpSpiderClientModel", back_populates="client_tasks")
    task = relationship("FpSpiderTaskModel", back_populates="client_tasks")
    status = Column(Integer, nullable=False, default=0, comment="执行状态：0-待执行，1-执行中，2-已完成，3-已失败")
    task_process = Column(Double, default=0.0, comment="任务进度，范围0-100")
    result = Column(String(255), comment="执行结果")
    result_id = Column(String(64), index=True, comment="MongoDB结果ID")
    start_time = Column(DateTime, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    create_time = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    update_time = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")