from pydantic import BaseModel


class TaskStartPO(BaseModel):
    task_id: int