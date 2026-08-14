from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Double, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression

from server.app.db.database import Base


class FpSpiderClientModel(Base):
    """Spider browser/client instance."""

    __tablename__ = "fp_spider_client"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True, comment="primary key")
    client_name = Column(String(50), nullable=False, index=True, comment="client name")
    device_id = Column(String(64), unique=True, index=True, comment="unique device id")
    ip_address = Column(String(39), comment="IP address")
    admin_id = Column(Integer, ForeignKey("user.id"), nullable=True, comment="admin/employee id")
    admin = relationship("User", back_populates="spider_clients")
    status = Column(Integer, nullable=False, default=1, comment="0-disabled, 1-enabled")
    is_online = Column(Boolean, nullable=False, server_default=expression.false(), comment="online state")
    create_time = Column(DateTime, nullable=False, default=datetime.utcnow, comment="created at")
    update_time = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="updated at")
    client_tasks = relationship("FpSpiderClientTaskModel", back_populates="client", cascade="all, delete-orphan")


class FpSpiderTaskModel(Base):
    """Spider task."""

    __tablename__ = "fp_spider_task"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True, comment="primary key")
    spider_task_title = Column(String(128), nullable=False, index=True, comment="task title")
    task_type = Column(Integer, nullable=False, comment="task type")
    status = Column(Integer, nullable=False, default=0, comment="0-pending, 1-running, 2-done, 3-failed")
    start_time = Column(DateTime, comment="started at")
    end_time = Column(DateTime, comment="ended at")
    head_users = Column(Integer, default=0, comment="head user count")
    client_tasks = relationship("FpSpiderClientTaskModel", back_populates="task", cascade="all, delete-orphan")


class FpSpiderClientTaskModel(Base):
    """Relation between a spider client and a spider task."""

    __tablename__ = "fp_spider_client_task"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True, comment="primary key")
    client_id = Column(Integer, ForeignKey("fp_spider_client.id"), nullable=False, index=True, comment="client id")
    task_id = Column(Integer, ForeignKey("fp_spider_task.id"), nullable=False, index=True, comment="task id")
    client = relationship("FpSpiderClientModel", back_populates="client_tasks")
    task = relationship("FpSpiderTaskModel", back_populates="client_tasks")
    status = Column(Integer, nullable=False, default=0, comment="0-pending, 1-running, 2-done, 3-failed")
    task_process = Column(Double, default=0.0, comment="task progress 0-100")
    result = Column(String(255), comment="result")
    result_id = Column(String(64), index=True, comment="MongoDB result id")
    start_time = Column(DateTime, comment="started at")
    end_time = Column(DateTime, comment="ended at")
    create_time = Column(DateTime, nullable=False, default=datetime.utcnow, comment="created at")
    update_time = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="updated at")
