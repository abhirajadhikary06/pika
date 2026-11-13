"""Celery worker entrypoint."""
from app import create_app, celery

app = create_app()
app.app_context().push()

# Import tasks so they are registered
from app.tasks import notifications, cleanup  # noqa: F401, E402
