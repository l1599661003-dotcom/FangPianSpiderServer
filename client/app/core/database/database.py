from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session

# 数据库连接配置
DATABASE_URL = 'mysql+pymysql://root:root@localhost:3306/fp_project'
# DATABASE_URL = 'mysql+pymysql://root:root@localhost:3306/tibao_2'

# 创建数据库引擎
engine = create_engine(DATABASE_URL, isolation_level="READ UNCOMMITTED")

# 创建会话工厂
Session = sessionmaker(bind=engine)
ScopedSession = scoped_session(Session)

# 创建会话
session = Session()

# try:
#     result = session.execute(text("SELECT VERSION()")).scalar()
#     print(f"数据库连接成功！数据库版本: {result}")
# except Exception as e:
#     print(f"数据库连接失败: {e}")
# finally:
#     # 关闭会话
#     session.close()
