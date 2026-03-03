"""Pydantic models for the remote supervisor API."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class ServiceStatusResponse(BaseModel):
    """Status details for the monitored service."""

    unit: str = Field(..., description="systemd unit name")
    active_state: Optional[str] = Field(None, description="High-level active state")
    sub_state: Optional[str] = Field(None, description="Detailed state")
    result: Optional[str] = Field(None, description="Last result code")
    pid: Optional[int] = Field(None, description="Main process identifier")
    unit_file_state: Optional[str] = Field(None, description="Unit enablement state")
    started_at: Optional[datetime] = Field(None, description="Last time the unit entered active state")
    uptime_seconds: Optional[float] = Field(None, description="Seconds the unit has been running")


class ServiceActionResponse(ServiceStatusResponse):
    """Response emitted after mutating the service state."""

    action: str = Field(..., description="Action requested by the client")


class MetricsResponse(BaseModel):
    """Cycle statistics aggregated for dashboards."""

    machine_id: str
    last_cycle_seconds: Optional[float]
    window_averages: Dict[int, Optional[float]]


class ConfigSnapshot(BaseModel):
    """Current monitor configuration snapshot."""

    machine_id: str
    gpio_pin: int
    csv_path: str
    reset_hour: int


class StackLightState(BaseModel):
    """Current state of stack lights."""

    green: bool = Field(..., description="Green light state")
    amber: bool = Field(..., description="Amber/yellow light state")
    red: bool = Field(..., description="Red light state")
    flashing: bool = Field(False, description="Whether lights are currently flashing")
    flash_interval: Optional[float] = Field(None, description="Flash interval in seconds, if flashing")
    last_updated: Optional[str] = Field(None, description="ISO timestamp of last update")


class StackLightSetRequest(BaseModel):
    """Request to set stack light states."""

    green: bool = Field(..., description="Green light state")
    amber: bool = Field(..., description="Amber/yellow light state")
    red: bool = Field(..., description="Red light state")


class StackLightFlashRequest(BaseModel):
    """Request to flash stack lights."""

    green: bool = Field(False, description="Flash green light")
    amber: bool = Field(False, description="Flash amber/yellow light")
    red: bool = Field(False, description="Flash red light")
    interval: float = Field(0.5, description="Flash interval in seconds (on/off cycle)", ge=0.1, le=5.0)


class StackLightResponse(BaseModel):
    """Response from stack light operations."""

    success: bool = Field(..., description="Whether the operation succeeded")
    state: Optional[StackLightState] = Field(None, description="Current light state")
    message: Optional[str] = Field(None, description="Status or error message")
    timestamp: Optional[str] = Field(None, description="ISO timestamp of response")
    error: Optional[str] = Field(None, description="Error details if failed")


class SystemActionResponse(BaseModel):
    """Response from system-level operations like reboot."""

    action: str = Field(..., description="Action requested by the client")
    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Status or error message")
