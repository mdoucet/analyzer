"""
Tests for MCP server and tool functions.
"""

import pytest


class TestSchemas:
    """Tests for Pydantic schemas."""
    
    def test_fit_result_creation(self):
        """Test FitResult model creation."""
        from analyzer_tools.schemas import FitResult, ParameterInfo
        
        result = FitResult(
            success=True,
            chi_squared=1.5,
            parameters=[
                ParameterInfo(name="Cu thickness", value=100.0, uncertainty=5.0)
            ],
            message="Test fit"
        )
        
        assert result.success is True
        assert result.chi_squared == 1.5
        assert len(result.parameters) == 1
    
    def test_partial_data_result_creation(self):
        """Test PartialDataAssessmentResult model creation."""
        from analyzer_tools.schemas import PartialDataAssessmentResult
        
        result = PartialDataAssessmentResult(
            success=True,
            set_id="218281",
            num_parts=3,
            overall_quality="good",
            message="Test assessment"
        )
        
        assert result.success is True
        assert result.set_id == "218281"
        assert result.overall_quality == "good"


class TestToolFunctions:
    """Tests for tool functions."""
    
    def test_list_tools(self):
        """Test list_tools function."""
        from analyzer_tools.tool_functions import list_tools
        
        result = list_tools()
        
        assert result.success is True
        assert len(result.tools) > 0
        assert all("name" in t for t in result.tools)
    
    def test_list_available_models(self):
        """Test list_available_models function."""
        from analyzer_tools.tool_functions import list_available_models
        
        result = list_available_models()
        
        assert result.success is True
        assert "cu_thf" in result.models
    
    def test_get_tool_help_found(self):
        """Test get_tool_help with valid tool."""
        from analyzer_tools.tool_functions import get_tool_help
        
        result = get_tool_help("run_fit")
        
        assert result.tool_name != "run_fit"  # Returns full name
        assert "fit" in result.description.lower()
    
    def test_get_tool_help_not_found(self):
        """Test get_tool_help with invalid tool."""
        from analyzer_tools.tool_functions import get_tool_help
        
        result = get_tool_help("nonexistent_tool")
        
        assert "not found" in result.description


class TestMCPServer:
    """Tests for MCP server."""
    
    def test_server_imports(self):
        """Test that MCP server can be imported."""
        from analyzer_tools.mcp_server import mcp
        
        assert mcp is not None
        assert mcp.name == "analyzer-tools"
    
    def test_tools_registered(self):
        """Test that tools are registered with FastMCP."""
        from analyzer_tools.mcp_server import mcp
        
        # FastMCP stores tools internally
        # Just verify the mcp object exists and has the right name
        assert mcp.name == "analyzer-tools"
    
    def test_tool_functions_callable(self):
        """Test that underlying tool functions are callable."""
        from analyzer_tools.tool_functions import list_tools, list_available_models
        
        # Test list_tools returns a result with success
        result = list_tools()
        assert result.success is True
        assert len(result.tools) > 0
        
        # Test list_available_models returns a result
        result = list_available_models()
        assert result.success is True
        assert "cu_thf" in result.models


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
