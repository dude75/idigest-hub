"""Instance admin: workers, tariffs, settings, orgs, impersonate, audit, skills."""
from app.routers.instance._router import router
from app.routers.instance import audit, impersonate, orgs, settings, skills, tariffs, workers  # noqa: F401

__all__ = ["router"]
