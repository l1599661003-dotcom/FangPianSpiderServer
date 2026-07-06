from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime

# 用户模型
from server.app.db.database import Base


# 用户模型
class User(Base):
    __tablename__ = "fp_admin"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String(255))
    create_time = Column(DateTime, default=datetime.utcnow)
    salt = Column(String(32))

# 博主模型
class FpBloger(Base):
    __tablename__ = "fp_bloger"

    id = Column(Integer, primary_key=True, index=True)

