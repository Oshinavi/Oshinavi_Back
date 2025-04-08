import json
from typing import Any

from quart import current_app
from quart.json.provider import DefaultJSONProvider


class JSONEncoder(json.JSONEncoder):
    """A JSON encoder which uses the app.json_provider_class for the default"""

    def default(self, o: Any) -> Any:
        # If the registered JSON provider does not implement a default classmethod
        # use the method defined by the DefaultJSONProvider
        default = getattr(
            current_app.json_provider_class, "default", DefaultJSONProvider.default
        )
        return default(o)
