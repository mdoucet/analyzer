"""
Tests for analyzer_tools.registry module.
"""

from unittest.mock import patch

from analyzer_tools.registry import (
    ToolInfo, TOOLS, WORKFLOWS, 
    get_all_tools, get_tool, get_tools_by_data_type, 
    get_workflows, print_tool_overview
)


class TestToolInfo:
    """Test the ToolInfo class."""
    
    def test_tool_info_creation(self):
        """Test creating a ToolInfo instance."""
        tool = ToolInfo(
            name="Test Tool",
            module="test.module", 
            description="A test tool",
            usage="test command",
            examples=["test example"],
            data_type="combined"
        )
        
        assert tool.name == "Test Tool"
        assert tool.module == "test.module"
        assert tool.description == "A test tool"
        assert tool.usage == "test command"
        assert tool.examples == ["test example"]
        assert tool.data_type == "combined"
    
    def test_tool_info_default_data_type(self):
        """Test ToolInfo with default data_type."""
        tool = ToolInfo(
            name="Test Tool",
            module="test.module",
            description="A test tool", 
            usage="test command",
            examples=["test example"]
        )
        
        assert tool.data_type == "both"


class TestToolRegistry:
    """Test the tool registry functions."""
    
    def test_get_all_tools(self):
        """Test get_all_tools returns the TOOLS dict."""
        tools = get_all_tools()
        assert tools is TOOLS
        assert isinstance(tools, dict)
        assert len(tools) > 0
    
    def test_get_tool_existing(self):
        """Test get_tool for existing tool."""
        tool = get_tool("partial_data_assessor")
        assert tool is not None
        assert isinstance(tool, ToolInfo)
        assert tool.name == "Partial Data Assessor"
    
    def test_get_tool_nonexistent(self):
        """Test get_tool for non-existent tool."""
        tool = get_tool("nonexistent_tool")
        assert tool is None
    
    def test_get_tools_by_data_type_partial(self):
        """Test filtering tools by partial data type."""
        tools = get_tools_by_data_type("partial")
        
        # Should include tools marked as 'partial' or 'both'
        assert len(tools) > 0
        for name, tool in tools.items():
            assert tool.data_type in ["partial", "both"]
    
    def test_get_tools_by_data_type_combined(self):
        """Test filtering tools by combined data type."""
        tools = get_tools_by_data_type("combined")
        
        # Should include tools marked as 'combined' or 'both'
        assert len(tools) > 0
        for name, tool in tools.items():
            assert tool.data_type in ["combined", "both"]
    
    def test_get_workflows(self):
        """Test get_workflows returns the WORKFLOWS dict."""
        workflows = get_workflows()
        assert workflows is WORKFLOWS
        assert isinstance(workflows, dict)
        assert len(workflows) > 0
        
        # Check workflow structure
        for name, workflow in workflows.items():
            assert "name" in workflow
            assert "description" in workflow
            assert "steps" in workflow
            assert "tools" in workflow
            assert isinstance(workflow["steps"], list)
            assert isinstance(workflow["tools"], list)


class TestToolRegistryContent:
    """Test the content of the tool registry."""
    
    def test_tools_registry_has_expected_tools(self):
        """Test that TOOLS contains expected analysis tools."""
        expected_tools = [
            "partial_data_assessor",
            "run_fit", 
            "result_assessor",
            "create_model_script",
            "create_temporary_model"
        ]
        
        for tool_name in expected_tools:
            assert tool_name in TOOLS
            tool = TOOLS[tool_name]
            assert isinstance(tool, ToolInfo)
            assert tool.name
            assert tool.description
            assert tool.usage
            assert tool.examples
    
    def test_workflows_registry_has_expected_workflows(self):
        """Test that WORKFLOWS contains expected analysis workflows."""
        expected_workflows = [
            "partial_data_quality",
            "standard_fitting", 
            "parameter_exploration"
        ]
        
        for workflow_name in expected_workflows:
            assert workflow_name in WORKFLOWS
            workflow = WORKFLOWS[workflow_name]
            assert workflow["name"]
            assert workflow["description"]
            assert len(workflow["steps"]) > 0
            assert len(workflow["tools"]) > 0


class TestPrintToolOverview:
    """Test the print_tool_overview function."""
    
    @patch('builtins.print')
    def test_print_tool_overview_with_config(self, mock_print):
        """Test print_tool_overview with mocked config."""
        mock_data_org = {
            'combined_data_dir': 'test_combined',
            'partial_data_dir': 'test_partial', 
            'reports_dir': 'test_reports',
            'combined_data_template': 'TEST_{set_id}_data.txt',
            'models_dir': 'test_models'
        }
        
        with patch('analyzer_tools.config_utils.get_data_organization_info', return_value=mock_data_org):
            print_tool_overview()
            
            # Check that print was called
            assert mock_print.called
            
            # Combine all print calls to check content
            print_calls = [str(call) for call in mock_print.call_args_list]
            combined_output = " ".join(print_calls)
            
            # Should contain configured paths
            assert "test_combined" in combined_output
            assert "test_partial" in combined_output
            assert "TEST_{set_id}_data.txt" in combined_output
            
            # Should contain tool information
            assert "NEUTRON REFLECTOMETRY DATA ANALYSIS TOOLS" in combined_output
            assert "AVAILABLE ANALYSIS TOOLS" in combined_output
            assert "ANALYSIS WORKFLOWS" in combined_output
            assert "DATA ORGANIZATION" in combined_output
    
    @patch('builtins.print') 
    def test_print_tool_overview_fallback(self, mock_print):
        """Test print_tool_overview falls back gracefully when config fails."""
        # Simulate config import failure
        with patch('analyzer_tools.config_utils.get_data_organization_info', side_effect=ImportError):
            print_tool_overview()
            
            # Should still print something (with default values)
            assert mock_print.called
            
            print_calls = [str(call) for call in mock_print.call_args_list]
            combined_output = " ".join(print_calls)
            
            # Should contain default paths
            assert "data/combined" in combined_output
            assert "data/partial" in combined_output
