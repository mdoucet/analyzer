"""
Tests for MCP server and schemas.
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
            message="Test fit",
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
            message="Test assessment",
        )

        assert result.success is True
        assert result.set_id == "218281"
        assert result.overall_quality == "good"


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

        assert mcp.name == "analyzer-tools"

    def test_list_available_models(self):
        """Test list_available_models returns models."""
        from analyzer_tools.mcp_server import list_available_models

        result = list_available_models.fn()

        assert result["success"] is True
        assert "cu_thf" in result["models"]

    def test_list_available_data(self):
        """Test list_available_data returns a result."""
        from analyzer_tools.mcp_server import list_available_data

        result = list_available_data.fn()

        assert result["success"] is True
        assert "combined_data" in result
        assert "partial_data" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
