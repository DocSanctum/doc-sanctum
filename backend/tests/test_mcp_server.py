from backend.app.mcp.server import mcp


def test_mcp_tool_names_no_handler_suffix():
    """툴 이름에 _handler 접미사가 붙으면 MCP 클라이언트가 호출 불가 — 이름 검증."""
    tool_names = [tool.name for tool in mcp._tool_manager._tools.values()]
    assert "list_documents" in tool_names
    assert "read_document" in tool_names
    assert "search_documents" in tool_names


def test_mcp_tool_names_no_raw_handler():
    """함수명 그대로 노출된 _handler 이름이 없어야 한다."""
    tool_names = [tool.name for tool in mcp._tool_manager._tools.values()]
    for name in tool_names:
        assert not name.endswith("_handler"), f"툴 이름에 _handler 접미사: {name}"


def test_mcp_tool_count():
    """등록된 툴이 정확히 3개여야 한다."""
    tool_names = [tool.name for tool in mcp._tool_manager._tools.values()]
    assert len(tool_names) == 3
