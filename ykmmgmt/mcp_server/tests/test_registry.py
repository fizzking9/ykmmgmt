"""Tests for the file-based tool registry (discovery + schema validation)."""

from types import ModuleType

import pytest
from mcp_server.tools import ToolSpec, ToolSpecError, discover_tools


def _tool_module(**attrs) -> ModuleType:
    """Build a minimal well-formed tool module, overridable per test."""
    module = ModuleType("fake_tool")

    async def handler(client, arguments):  # pragma: no cover — shape only
        return {}

    module.name = "fake_tool"
    module.description = "A fake tool for registry tests."
    module.input_schema = {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "required": ["x"],
    }
    module.handler = handler
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


# ── Discovery ────────────────────────────────────────────────────────────────


def test_discover_tools_finds_export_visualizations():
    specs = discover_tools()
    names = [s.name for s in specs]
    assert "export_visualizations" in names


def test_discovered_tool_shape_is_valid():
    specs = {s.name: s for s in discover_tools()}
    spec = specs["export_visualizations"]
    assert spec.description
    assert spec.input_schema["type"] == "object"
    assert "output_dir" in spec.input_schema["properties"]
    assert spec.input_schema["required"] == ["output_dir"]
    assert callable(spec.handler)


def test_discovery_skips_private_modules():
    # The only real modules are __init__ (package marker) and the tool itself
    specs = discover_tools()
    assert all(not s.name.startswith("_") for s in specs)


# ── ToolSpec validation ──────────────────────────────────────────────────────


def test_from_module_rejects_missing_attributes():
    module = _tool_module()
    del module.handler
    with pytest.raises(ToolSpecError, match="handler"):
        ToolSpec.from_module(module)


def test_from_module_rejects_empty_name():
    with pytest.raises(ToolSpecError, match="name"):
        ToolSpec.from_module(_tool_module(name=""))


def test_from_module_rejects_non_identifier_name():
    with pytest.raises(ToolSpecError, match="name"):
        ToolSpec.from_module(_tool_module(name="not a name"))


def test_from_module_rejects_empty_description():
    with pytest.raises(ToolSpecError, match="description"):
        ToolSpec.from_module(_tool_module(description=""))


def test_from_module_rejects_non_object_schema():
    with pytest.raises(ToolSpecError, match="input_schema"):
        ToolSpec.from_module(_tool_module(input_schema={"type": "array"}))


def test_from_module_rejects_schema_without_properties():
    with pytest.raises(ToolSpecError, match="properties"):
        ToolSpec.from_module(_tool_module(input_schema={"type": "object"}))


def test_from_module_rejects_required_not_subset_of_properties():
    schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["y"]}
    with pytest.raises(ToolSpecError, match="required"):
        ToolSpec.from_module(_tool_module(input_schema=schema))


def test_from_module_rejects_non_callable_handler():
    with pytest.raises(ToolSpecError, match="handler"):
        ToolSpec.from_module(_tool_module(handler="not-callable"))


def test_from_module_accepts_well_formed_module():
    spec = ToolSpec.from_module(_tool_module())
    assert spec.name == "fake_tool"
    assert spec.input_schema["required"] == ["x"]
