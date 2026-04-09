"""
src/routers/admin.py
管理员专用 API：入口模块，聚合所有 admin 子路由。
"""
from .admin_entities  import router as router_entities   # noqa: F401
from .admin_activity  import router as router_activity   # noqa: F401
from .admin_analytics import router as router_analytics  # noqa: F401
