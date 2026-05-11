try:
    from .api.main import app
except ImportError:
    from api.main import app
