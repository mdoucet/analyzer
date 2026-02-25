"""Pydantic schemas for MCP tool outputs.

These schemas define the structured return types used by MCP tools,
ensuring consistent and validated response interfaces.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# ============================================================================
# Common Types
# ============================================================================

class ParameterInfo(BaseModel):
    """Information about a model parameter."""
    name: str = Field(..., description="Parameter name")
    value: float = Field(..., description="Current/fitted value")
    uncertainty: Optional[float] = Field(None, description="Parameter uncertainty (1-sigma)")
    bounds: Optional[tuple] = Field(None, description="Parameter bounds (min, max)")
    units: Optional[str] = Field(None, description="Parameter units")


class DataFileInfo(BaseModel):
    """Information about a data file."""
    path: str = Field(..., description="Full path to the file")
    set_id: str = Field(..., description="Data set identifier")
    file_type: Literal["partial", "combined"] = Field(..., description="Type of data file")



class FitResult(BaseModel):
    """Result from a reflectivity fit."""
    success: bool = Field(..., description="Whether the fit completed successfully")
    chi_squared: Optional[float] = Field(None, description="Chi-squared value of the fit")
    reduced_chi_squared: Optional[float] = Field(None, description="Reduced chi-squared")
    parameters: List[ParameterInfo] = Field(default_factory=list, description="Fitted parameters")
    output_dir: Optional[str] = Field(None, description="Directory containing fit results")
    message: str = Field("", description="Status message or error description")


class AssessmentResult(BaseModel):
    """Result from fit assessment."""
    success: bool = Field(..., description="Whether assessment completed")
    quality: Literal["good", "acceptable", "poor", "failed"] = Field(
        ..., description="Overall quality rating"
    )
    chi_squared: Optional[float] = Field(None, description="Chi-squared value")
    recommendations: List[str] = Field(default_factory=list, description="Improvement recommendations")
    report_path: Optional[str] = Field(None, description="Path to generated report")
    message: str = Field("", description="Status message")


class PartialDataAssessmentResult(BaseModel):
    """Result from partial data assessment."""
    success: bool = Field(..., description="Whether assessment completed")
    set_id: str = Field(..., description="Set ID that was assessed")
    num_parts: int = Field(..., description="Number of partial data files found")
    overlap_quality: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Quality metrics for each overlap region"
    )
    overall_quality: Literal["good", "acceptable", "poor"] = Field(
        ..., description="Overall quality rating"
    )
    report_path: Optional[str] = Field(None, description="Path to generated report")
    message: str = Field("", description="Status message")


class EISIntervalsResult(BaseModel):
    """Result from EIS interval extraction."""
    success: bool = Field(..., description="Whether extraction completed")
    source_directory: str = Field(..., description="Source directory of EIS files")
    resolution: str = Field(..., description="Resolution mode used")
    n_files: int = Field(..., description="Number of files processed")
    n_intervals: int = Field(..., description="Number of intervals extracted")
    intervals: List[Dict[str, Any]] = Field(
        default_factory=list, description="Extracted intervals"
    )
    output_file: Optional[str] = Field(None, description="Output JSON file if saved")
    message: str = Field("", description="Status message")


class DataListResult(BaseModel):
    """Result from listing available data."""
    success: bool = Field(..., description="Whether listing completed")
    combined_data: List[DataFileInfo] = Field(
        default_factory=list, description="Available combined data files"
    )
    partial_data: List[DataFileInfo] = Field(
        default_factory=list, description="Available partial data files"
    )
    message: str = Field("", description="Status message")


class ModelListResult(BaseModel):
    """Result from listing available models."""
    success: bool = Field(..., description="Whether listing completed")
    models: List[str] = Field(default_factory=list, description="Available model names")
    message: str = Field("", description="Status message")

