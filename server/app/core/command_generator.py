from datetime import datetime
from typing import Dict, Any, Optional, List


class CommandGenerator:
    """命令生成器，用于生成标准格式的指令"""
    
    def generate_message(self, cmd: str, data: Dict[str, Any], task_id: Optional[str] = None, client_id: Optional[str] = None) -> Dict[str, Any]:
        """
        生成标准格式的指令消息
        
        Args:
            cmd: 命令类型
            data: 命令数据
            task_id: 任务ID，可选
            client_id: 客户端ID，可选
            
        Returns:
            标准格式的指令字典
        """
        message = {
            "cmd": cmd,
            "data": data,
            "timestamp": datetime.now().timestamp()
        }
        
        if task_id is not None:
            message["task_id"] = task_id
            
        if client_id is not None:
            message["client_id"] = client_id
            
        return message
    
    def generate_task_start(self, task_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成任务开始指令
        
        Args:
            task_id: 任务ID
            task_data: 任务数据
            
        Returns:
            任务开始指令字典
        """
        return self.generate_message("task_start", task_data, task_id)
    
    def generate_task_stop(self, task_id: str, reason: str = "") -> Dict[str, Any]:
        """
        生成任务停止指令
        
        Args:
            task_id: 任务ID
            reason: 停止原因，可选
            
        Returns:
            任务停止指令字典
        """
        return self.generate_message("task_stop", {"reason": reason}, task_id)
    
    def generate_data_push(self, task_id: str, data_list: list, batch_id: str) -> Dict[str, Any]:
        """
        生成数据推送指令
        
        Args:
            task_id: 任务ID
            data_list: 数据列表
            batch_id: 批次ID
            
        Returns:
            数据推送指令字典
        """
        return self.generate_message("data_push", {
            "data_list": data_list,
            "batch_id": batch_id,
            "count": len(data_list)
        }, task_id)
    
    def generate_heartbeat(self) -> Dict[str, Any]:
        """
        生成心跳检测指令
        
        Returns:
            心跳检测指令字典
        """
        return self.generate_message("heartbeat", {})
    
    def generate_error(self, error_code: str, error_message: str, task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        生成错误指令
        
        Args:
            error_code: 错误代码
            error_message: 错误消息
            task_id: 任务ID，可选
            
        Returns:
            错误指令字典
        """
        return self.generate_message("error", {
            "code": error_code,
            "message": error_message
        }, task_id)
        
    def generate_token_response(self, task_id: str, token_id: str, token_content: Any) -> Dict[str, Any]:
        """
        生成令牌响应指令
        
        Args:
            task_id: 任务ID
            token_id: 令牌ID
            token_content: 令牌内容
            
        Returns:
            令牌响应指令字典
        """
        return self.generate_message("token_response", {
            "token_id": token_id,
            "token_content": token_content
        }, task_id)
        
    def generate_result_confirm(self, task_id: str, status: str, message: str = "") -> Dict[str, Any]:
        """
        生成结果确认指令
        
        Args:
            task_id: 任务ID
            status: 状态，"success"或"error"
            message: 消息，可选
            
        Returns:
            结果确认指令字典
        """
        return self.generate_message("result_confirm", {
            "status": status,
            "message": message,
            "timestamp": datetime.now().timestamp()
        }, task_id)
    
    def generate_progress_update(self, task_id: str, progress: int, message: str = "") -> Dict[str, Any]:
        """
        生成进度更新指令
        
        Args:
            task_id: 任务ID
            progress: 进度值（0-100）
            message: 进度消息，可选
            
        Returns:
            进度更新指令字典
        """
        # 确保进度值在有效范围内
        progress = max(0, min(100, progress))
        
        return self.generate_message("progress_update", {
            "progress": progress,
            "message": message,
            "timestamp": datetime.now().timestamp()
        }, task_id)
    
    def generate_processing_notification(self, task_id: str, message: str, progress: int = 0) -> Dict[str, Any]:
        """
        生成处理中通知指令
        
        Args:
            task_id: 任务ID
            message: 处理消息
            progress: 进度值（0-100），可选
            
        Returns:
            处理中通知指令字典
        """
        # 确保进度值在有效范围内
        progress = max(0, min(100, progress))
        
        return self.generate_message("processing", {
            "message": message,
            "progress": progress,
            "timestamp": datetime.now().timestamp()
        }, task_id) 