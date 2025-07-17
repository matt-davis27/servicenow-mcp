"""
Incident tools for the ServiceNow MCP server.

This module provides tools for managing incidents in ServiceNow.
"""

import logging
from typing import Optional, List

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


class CreateIncidentParams(BaseModel):
    """Parameters for creating an incident."""

    short_description: str = Field(..., description="Short description of the incident")
    description: Optional[str] = Field(None, description="Detailed description of the incident")
    caller_id: Optional[str] = Field(None, description="User who reported the incident")
    category: Optional[str] = Field(None, description="Category of the incident")
    subcategory: Optional[str] = Field(None, description="Subcategory of the incident")
    priority: Optional[str] = Field(None, description="Priority of the incident")
    impact: Optional[str] = Field(None, description="Impact of the incident")
    urgency: Optional[str] = Field(None, description="Urgency of the incident")
    assigned_to: Optional[str] = Field(None, description="User assigned to the incident")
    assignment_group: Optional[str] = Field(None, description="Group assigned to the incident")


class UpdateIncidentParams(BaseModel):
    """Parameters for updating an incident."""

    incident_id: str = Field(..., description="Incident ID or sys_id")
    short_description: Optional[str] = Field(None, description="Short description of the incident")
    description: Optional[str] = Field(None, description="Detailed description of the incident")
    state: Optional[str] = Field(None, description="State of the incident")
    category: Optional[str] = Field(None, description="Category of the incident")
    subcategory: Optional[str] = Field(None, description="Subcategory of the incident")
    priority: Optional[str] = Field(None, description="Priority of the incident")
    impact: Optional[str] = Field(None, description="Impact of the incident")
    urgency: Optional[str] = Field(None, description="Urgency of the incident")
    assigned_to: Optional[str] = Field(None, description="User assigned to the incident")
    assignment_group: Optional[str] = Field(None, description="Group assigned to the incident")
    work_notes: Optional[str] = Field(None, description="Work notes to add to the incident")
    close_notes: Optional[str] = Field(None, description="Close notes to add to the incident")
    close_code: Optional[str] = Field(None, description="Close code for the incident")


class AddCommentParams(BaseModel):
    """Parameters for adding a comment to an incident."""

    incident_id: str = Field(..., description="Incident ID or sys_id")
    comment: str = Field(..., description="Comment to add to the incident")
    is_work_note: bool = Field(False, description="Whether the comment is a work note")


class ResolveIncidentParams(BaseModel):
    """Parameters for resolving an incident."""

    incident_id: str = Field(..., description="Incident ID or sys_id")
    resolution_code: str = Field(..., description="Resolution code for the incident")
    resolution_notes: str = Field(..., description="Resolution notes for the incident")


class ListIncidentsParams(BaseModel):
    """Parameters for listing incidents."""
    
    limit: int = Field(10, description="Maximum number of incidents to return", ge=1, le=1000)
    offset: int = Field(0, description="Offset for pagination", ge=0)
    state: Optional[str] = Field(None, description="Filter by incident state")
    assigned_to: Optional[str] = Field(None, description="Filter by assigned user")
    category: Optional[str] = Field(None, description="Filter by category", examples=["Hardware", "Software", "Network", "Inquiry / Help"])
    priority: Optional[str] = Field(None, description="Filter by priority (1-5 or P0-P4)", pattern=r"^(P[0-4X]|[1-5])$")
    number: Optional[str] = Field(None, description="Filter by incident number", pattern=r"^INC\d{7}$")
    query: Optional[str] = Field(None, description="Search query for incidents (searches short_description and description)")
    date_filters: Optional[dict] = Field(None, description="Dynamic date filters. Format: {'field_name': {'from': 'YYYY-MM-DD', 'to': 'YYYY-MM-DD'}}. Examples: {'sys_created_on': {'from': '2024-01-01'}, 'due_date': {'to': '2024-12-31'}, 'opened_at': {'from': '2024-01-01', 'to': '2024-01-31'}}")


class IncidentResponse(BaseModel):
    """Response from incident operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")
    incident_id: Optional[str] = Field(None, description="ID of the affected incident")
    incident_number: Optional[str] = Field(None, description="Number of the affected incident")


def create_incident(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateIncidentParams,
) -> IncidentResponse:
    """
    Create a new incident in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for creating the incident.

    Returns:
        Response with the created incident details.
    """
    api_url = f"{config.api_url}/table/incident"

    # Build request data
    data = {
        "short_description": params.short_description,
    }

    if params.description:
        data["description"] = params.description
    if params.caller_id:
        data["caller_id"] = params.caller_id
    if params.category:
        data["category"] = params.category
    if params.subcategory:
        data["subcategory"] = params.subcategory
    if params.priority:
        data["priority"] = params.priority
    if params.impact:
        data["impact"] = params.impact
    if params.urgency:
        data["urgency"] = params.urgency
    if params.assigned_to:
        data["assigned_to"] = params.assigned_to
    if params.assignment_group:
        data["assignment_group"] = params.assignment_group

    # Make request
    try:
        response = requests.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return IncidentResponse(
            success=True,
            message="Incident created successfully",
            incident_id=result.get("sys_id"),
            incident_number=result.get("number"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create incident: {e}")
        return IncidentResponse(
            success=False,
            message=f"Failed to create incident: {str(e)}",
        )


def update_incident(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateIncidentParams,
) -> IncidentResponse:
    """
    Update an existing incident in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for updating the incident.

    Returns:
        Response with the updated incident details.
    """
    # Determine if incident_id is a number or sys_id
    incident_id = params.incident_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        # This is likely a sys_id
        api_url = f"{config.api_url}/table/incident/{incident_id}"
    else:
        # This is likely an incident number
        # First, we need to get the sys_id
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
            }

            response = requests.get(
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()

            result = response.json().get("result", [])
            if not result:
                return IncidentResponse(
                    success=False,
                    message=f"Incident not found: {incident_id}",
                )

            incident_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{incident_id}"

        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return IncidentResponse(
                success=False,
                message=f"Failed to find incident: {str(e)}",
            )

    # Build request data
    data = {}

    if params.short_description:
        data["short_description"] = params.short_description
    if params.description:
        data["description"] = params.description
    if params.state:
        data["state"] = params.state
    if params.category:
        data["category"] = params.category
    if params.subcategory:
        data["subcategory"] = params.subcategory
    if params.priority:
        data["priority"] = params.priority
    if params.impact:
        data["impact"] = params.impact
    if params.urgency:
        data["urgency"] = params.urgency
    if params.assigned_to:
        data["assigned_to"] = params.assigned_to
    if params.assignment_group:
        data["assignment_group"] = params.assignment_group
    if params.work_notes:
        data["work_notes"] = params.work_notes
    if params.close_notes:
        data["close_notes"] = params.close_notes
    if params.close_code:
        data["close_code"] = params.close_code

    # Make request
    try:
        response = requests.put(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return IncidentResponse(
            success=True,
            message="Incident updated successfully",
            incident_id=result.get("sys_id"),
            incident_number=result.get("number"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to update incident: {e}")
        return IncidentResponse(
            success=False,
            message=f"Failed to update incident: {str(e)}",
        )


def add_comment(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: AddCommentParams,
) -> IncidentResponse:
    """
    Add a comment to an incident in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for adding the comment.

    Returns:
        Response with the result of the operation.
    """
    # Determine if incident_id is a number or sys_id
    incident_id = params.incident_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        # This is likely a sys_id
        api_url = f"{config.api_url}/table/incident/{incident_id}"
    else:
        # This is likely an incident number
        # First, we need to get the sys_id
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
            }

            response = requests.get(
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()

            result = response.json().get("result", [])
            if not result:
                return IncidentResponse(
                    success=False,
                    message=f"Incident not found: {incident_id}",
                )

            incident_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{incident_id}"

        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return IncidentResponse(
                success=False,
                message=f"Failed to find incident: {str(e)}",
            )

    # Build request data
    data = {}

    if params.is_work_note:
        data["work_notes"] = params.comment
    else:
        data["comments"] = params.comment

    # Make request
    try:
        response = requests.put(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return IncidentResponse(
            success=True,
            message="Comment added successfully",
            incident_id=result.get("sys_id"),
            incident_number=result.get("number"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to add comment: {e}")
        return IncidentResponse(
            success=False,
            message=f"Failed to add comment: {str(e)}",
        )


def resolve_incident(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ResolveIncidentParams,
) -> IncidentResponse:
    """
    Resolve an incident in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for resolving the incident.

    Returns:
        Response with the result of the operation.
    """
    # Determine if incident_id is a number or sys_id
    incident_id = params.incident_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        # This is likely a sys_id
        api_url = f"{config.api_url}/table/incident/{incident_id}"
    else:
        # This is likely an incident number
        # First, we need to get the sys_id
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
            }

            response = requests.get(
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()

            result = response.json().get("result", [])
            if not result:
                return IncidentResponse(
                    success=False,
                    message=f"Incident not found: {incident_id}",
                )

            incident_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{incident_id}"

        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return IncidentResponse(
                success=False,
                message=f"Failed to find incident: {str(e)}",
            )

    # Build request data
    data = {
        "state": "6",  # Resolved
        "close_code": params.resolution_code,
        "close_notes": params.resolution_notes,
        "resolved_at": "now",
    }

    # Make request
    try:
        response = requests.put(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return IncidentResponse(
            success=True,
            message="Incident resolved successfully",
            incident_id=result.get("sys_id"),
            incident_number=result.get("number"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to resolve incident: {e}")
        return IncidentResponse(
            success=False,
            message=f"Failed to resolve incident: {str(e)}",
        )


def list_incidents(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListIncidentsParams,
) -> dict:
    """
    List incidents from ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for listing incidents.

    Returns:
        Dictionary with list of incidents.
    """
    api_url = f"{config.api_url}/table/incident"

    # Build query parameters
    query_params = {
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_query_category": "reporting"
    }
    
    # Add filters
    filters = []
    if params.state:
        filters.append(f"state={params.state}")
    if params.assigned_to:
        filters.append(f"assigned_to={params.assigned_to}")
    if params.category:
        filters.append(f"category={params.category}")
    if params.priority:
        if params.priority.isdigit():
            filters.append(f"priority={params.priority}")
        else:
            priority_mapping = {'PX': -1, 'P0': 1, 'P1': 2, 'P2': 3, 'P3': 4, 'P4': 5}
            filters.append(f"priority={priority_mapping[params.priority]}")
    if params.number:
        filters.append(f"number={params.number}")
    if params.query:
        filters.append(f"short_descriptionLIKE{params.query}^ORdescriptionLIKE{params.query}")
    
    # Add date range filters
    def build_date_filter(field: str, date_from: str = None, date_to: str = None) -> str:
        """Build a date range filter for ServiceNow."""
        if not date_from and not date_to:
            return ""
        
        # Format dates for ServiceNow javascript functions
        def format_date(date_str: str, is_end_of_range: bool = False) -> str:
            # If only date provided (YYYY-MM-DD), add time
            if len(date_str) == 10:  # YYYY-MM-DD format
                time_part = "23:59:59" if is_end_of_range else "00:00:00"
                date_str = f"{date_str} {time_part}"
            # Convert to format: YYYY-MM-DD HH:MM:SS
            return date_str.replace(" ", "','")
        
        if date_from and date_to:  # Date range
            return f"{field}BETWEENjavascript:gs.dateGenerate('{format_date(date_from, False)}')@javascript:gs.dateGenerate('{format_date(date_to, True)}')"
        elif date_from:  # From date only
            return f"{field}>=javascript:gs.dateGenerate('{format_date(date_from, False)}')"
        else:  # To date only
            return f"{field}<=javascript:gs.dateGenerate('{format_date(date_to, True)}')"
    
    # Build dynamic date filters
    if params.date_filters:
        for field_name, date_range in params.date_filters.items():
            date_from = date_range.get('from', None)
            date_to = date_range.get('to', None)
            
            date_filter = build_date_filter(field_name, date_from, date_to)
            if date_filter:
                filters.append(date_filter)
    
    if filters:
        query_params["sysparm_query"] = "^".join(filters)

    logger.info(f"Listing incidents with query params: {query_params}")
    
    # Make request
    try:
        response = requests.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        
        data = response.json()
        incidents = []
        
        for incident_data in data.get("result", []):
            # Start with all fields from the API response
            incident = dict(incident_data)
            
            # Handle assigned_to field which could be a string or a dictionary
            assigned_to = incident_data.get("assigned_to")
            if isinstance(assigned_to, dict):
                incident["assigned_to"] = assigned_to.get("display_value")
            
            incidents.append(incident)
        
        return {
            "success": True,
            "message": f"Found {len(incidents)} incidents",
            "incidents": incidents
        }
        
    except requests.RequestException as e:
        logger.error(f"Failed to list incidents: {e}")
        return {
            "success": False,
            "message": f"Failed to list incidents: {str(e)}",
            "incidents": []
        }
