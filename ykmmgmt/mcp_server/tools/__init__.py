"""Tool registry — file-based auto-discovery of MCP tools.

A tool is a module inside this package (``tools/``) that defines:

- ``name`` — tool name exposed to MCP clients (snake_case string)
- ``description`` — one-paragraph description of what the tool does
- ``input_schema`` — JSON Schema (object) for the tool's arguments
- ``handler`` — ``async def handler(client: BackendClient, arguments: dict) -> dict``

Adding a new tool = dropping a new module into ``tools/``; no central
registry file to maintain. Modules whose names start with ``_`` are
ignored (helpers, not tools).
"""

import importlib
import pkgutil
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import Any

from mcp_server.client import BackendClient

Handler = Callable[[BackendClient, dict], Awaitable[dict[str, Any]]]

_REQUIRED_ATTRS = ("name", "description", "input_schema", "handler")


class ToolSpecError(Exception):
    """A tool module does not conform to the registry contract."""


class ToolSpec:
    """A validated tool module ready for registration with the MCP server."""

    def __init__(self, name: str, description: str, input_schema: dict, handler: Handler):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler

    @classmethod
    def from_module(cls, module: ModuleType) -> "ToolSpec":
        """Validate a module's tool attributes and build a ToolSpec."""
        missing = [attr for attr in _REQUIRED_ATTRS if not hasattr(module, attr)]
        if missing:
            raise ToolSpecError(f"工具模块 {module.__name__} 缺少必需属性: {', '.join(missing)}")

        name = module.name
        if not isinstance(name, str) or not name or not name.isidentifier():
            raise ToolSpecError(f"工具模块 {module.__name__} 的 name 必须是非空合法标识符")
        if not isinstance(module.description, str) or not module.description:
            raise ToolSpecError(f"工具模块 {module.__name__} 的 description 必须是非空字符串")

        schema = module.input_schema
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ToolSpecError(f"工具模块 {module.__name__} 的 input_schema 必须是 object 类型的 JSON Schema")
        if "properties" not in schema:
            raise ToolSpecError(f"工具模块 {module.__name__} 的 input_schema 缺少 properties")
        required = schema.get("required", [])
        if not isinstance(required, list) or not all(isinstance(r, str) for r in required):
            raise ToolSpecError(f"工具模块 {module.__name__} 的 input_schema.required 必须是字符串数组")
        if not set(required) <= set(schema["properties"]):
            raise ToolSpecError(f"工具模块 {module.__name__} 的 required 引用了不存在的属性")

        if not callable(module.handler):
            raise ToolSpecError(f"工具模块 {module.__name__} 的 handler 必须是可调用对象")

        return cls(name, module.description, schema, module.handler)


def discover_tools() -> list[ToolSpec]:
    """Import every tool module in this package and return its ToolSpec."""
    specs: list[ToolSpec] = []
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        specs.append(ToolSpec.from_module(module))
    specs.sort(key=lambda s: s.name)
    return specs
