from client.app.tasks.blogger_info_task import BloggerInfoTask
from client.app.tasks.blogger_detail_task import BloggerDetailTask
from client.app.tasks.training_blogger_task import TrainingBloggerTask


def register_tasks(task_manager):
    """
    注册所有任务处理器
    
    Args:
        task_manager: 任务管理器
    """
    # 注册博主信息采集任务处理器
    task_manager.register_task_class(0, TrainingBloggerTask)
    
    # 注册博主详情采集任务处理器
    task_manager.register_task_class(1, BloggerDetailTask)
