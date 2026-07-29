"""Table-specific cleaning rule registry.

Each table can register custom cleaning steps that run after the common
pipeline. Rules are keyed by English table name.
"""

from collections.abc import Callable

import pandas as pd

from app.services.cleaning import CleaningReport

# Type for a table-specific cleaning function
TableRule = Callable[[pd.DataFrame, CleaningReport], tuple[pd.DataFrame, CleaningReport]]

_registry: dict[str, list[TableRule]] = {}


def register(table_name: str) -> Callable[[TableRule], TableRule]:
    """Decorator to register a table-specific cleaning rule."""

    def wrapper(fn: TableRule) -> TableRule:
        if table_name not in _registry:
            _registry[table_name] = []
        _registry[table_name].append(fn)
        return fn

    return wrapper


def get_rules(table_name: str) -> list[TableRule]:
    """Get all registered rules for a table, in registration order."""
    return _registry.get(table_name, [])
