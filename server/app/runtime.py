"""Process-wide runtime singletons for the spider service.

WebSocket connections are kept in memory, so every route and scheduler must use
the exact same manager objects. Keeping these singletons outside `main.py`
prevents duplicate state when the app is started with `python -m server.app.main`.
"""

from server.app.core.PluginWebSocketManager import PluginWebSocketManager
from server.app.core.TaskScheduler import TaskScheduler
from server.app.core.WebSocketManager import WebSocketManager
from server.app.services.PluginRemoteControlService import PluginRemoteControlService
from server.app.services.PluginTriggerScheduler import PluginTriggerScheduler


ws_manager = WebSocketManager()
task_scheduler = TaskScheduler(ws_manager)

plugin_ws_manager = PluginWebSocketManager()
plugin_remote_service = PluginRemoteControlService(plugin_ws_manager)
plugin_trigger_scheduler = PluginTriggerScheduler(plugin_remote_service)
