"""
Tests for OpenAPI schema validation.

Verifies OpenAPI schema structure and consistency.
"""

import pytest
from src.adapt_rca.api.openapi_schema import get_openapi_schema, OPENAPI_SCHEMA


def test_openapi_schema_structure():
    """Test OpenAPI schema has required top-level fields."""
    schema = get_openapi_schema()
    
    required_fields = ["openapi", "info", "paths", "components"]
    for field in required_fields:
        assert field in schema, f"Missing required field: {field}"


def test_openapi_version():
    """Test OpenAPI version is 3.0.0."""
    schema = get_openapi_schema()
    assert schema["openapi"] == "3.0.0"


def test_api_info():
    """Test API info section."""
    schema = get_openapi_schema()
    info = schema["info"]
    
    assert "title" in info
    assert "description" in info
    assert "version" in info
    assert info["title"] == "ADAPT-RCA API"
    assert info["version"] == "5.0.0-alpha"


def test_api_paths_exist():
    """Test required API paths are defined."""
    schema = get_openapi_schema()
    paths = schema["paths"]
    
    required_paths = ["/health", "/readiness", "/version", "/rca", "/rca/{incident_id}"]
    for path in required_paths:
        assert path in paths, f"Missing required path: {path}"


def test_health_endpoint_schema():
    """Test health endpoint schema."""
    schema = get_openapi_schema()
    health = schema["paths"]["/health"]["get"]
    
    assert "summary" in health
    assert "responses" in health
    assert "200" in health["responses"]
    
    response_schema = health["responses"]["200"]["content"]["application/json"]["schema"]
    assert "$ref" in response_schema
    assert response_schema["$ref"] == "#/components/schemas/HealthResponse"


def test_rca_endpoint_schema():
    """Test RCA endpoint schema."""
    schema = get_openapi_schema()
    rca = schema["paths"]["/rca"]["post"]
    
    assert "summary" in rca
    assert "requestBody" in rca
    assert "responses" in rca
    
    # Check request body
    request_body = rca["requestBody"]
    assert request_body["required"] is True
    request_schema = request_body["content"]["application/json"]["schema"]
    assert "$ref" in request_schema
    
    # Check responses
    assert "200" in rca["responses"]
    assert "400" in rca["responses"]


def test_component_schemas_defined():
    """Test all referenced component schemas are defined."""
    schema = get_openapi_schema()
    components = schema["components"]["schemas"]
    
    required_schemas = [
        "HealthResponse",
        "ReadinessResponse",
        "VersionResponse",
        "RCARequest",
        "RCAResponse",
        "StatusResponse",
        "ErrorResponse"
    ]
    
    for schema_name in required_schemas:
        assert schema_name in components, f"Missing schema: {schema_name}"


def test_health_response_schema():
    """Test HealthResponse schema structure."""
    schema = get_openapi_schema()
    health_response = schema["components"]["schemas"]["HealthResponse"]
    
    assert health_response["type"] == "object"
    assert "required" in health_response
    
    required_fields = health_response["required"]
    assert "status" in required_fields
    assert "uptime_seconds" in required_fields
    assert "service" in required_fields
    assert "version" in required_fields


def test_rca_request_schema():
    """Test RCARequest schema structure."""
    schema = get_openapi_schema()
    rca_request = schema["components"]["schemas"]["RCARequest"]
    
    assert rca_request["type"] == "object"
    assert "events" in rca_request["required"]
    
    properties = rca_request["properties"]
    assert "events" in properties
    assert properties["events"]["type"] == "array"
    assert "minItems" in properties["events"]
    assert properties["events"]["minItems"] == 1


def test_rca_response_schema():
    """Test RCAResponse schema structure."""
    schema = get_openapi_schema()
    rca_response = schema["components"]["schemas"]["RCAResponse"]
    
    assert rca_response["type"] == "object"
    assert "status" in rca_response["required"]
    assert "incident_id" in rca_response["required"]
    
    properties = rca_response["properties"]
    assert "status" in properties
    assert "incident_id" in properties
    assert "root_causes" in properties
    assert "recommendations" in properties


def test_error_response_schema():
    """Test ErrorResponse schema structure."""
    schema = get_openapi_schema()
    error_response = schema["components"]["schemas"]["ErrorResponse"]
    
    assert error_response["type"] == "object"
    assert "error" in error_response["required"]
    
    properties = error_response["properties"]
    assert "error" in properties
    assert properties["error"]["type"] == "string"


def test_status_response_schema():
    """Test StatusResponse schema structure."""
    schema = get_openapi_schema()
    status_response = schema["components"]["schemas"]["StatusResponse"]
    
    assert status_response["type"] == "object"
    assert "incident_id" in status_response["required"]
    assert "status" in status_response["required"]
    
    properties = status_response["properties"]
    assert "progress" in properties
    assert properties["progress"]["minimum"] == 0
    assert properties["progress"]["maximum"] == 100


def test_all_paths_have_operation_ids():
    """Test all endpoints have operation IDs."""
    schema = get_openapi_schema()
    
    for path, methods in schema["paths"].items():
        for method, details in methods.items():
            assert "operationId" in details, \
                f"Missing operationId for {method.upper()} {path}"


def test_all_paths_have_tags():
    """Test all endpoints have tags."""
    schema = get_openapi_schema()
    
    for path, methods in schema["paths"].items():
        for method, details in methods.items():
            assert "tags" in details, \
                f"Missing tags for {method.upper()} {path}"


def test_schema_immutability():
    """Test get_openapi_schema returns a copy."""
    schema1 = get_openapi_schema()
    schema2 = get_openapi_schema()
    
    # Modify first schema
    schema1["info"]["title"] = "Modified"
    
    # Second schema should be unchanged
    assert schema2["info"]["title"] == "ADAPT-RCA API"


def test_servers_defined():
    """Test API servers are defined."""
    schema = get_openapi_schema()
    
    assert "servers" in schema
    assert len(schema["servers"]) > 0
    
    server = schema["servers"][0]
    assert "url" in server
    assert "description" in server


def test_contact_and_license_info():
    """Test contact and license information present."""
    schema = get_openapi_schema()
    info = schema["info"]
    
    assert "contact" in info
    assert "name" in info["contact"]
    
    assert "license" in info
    assert "name" in info["license"]


def test_response_content_types():
    """Test all responses specify content type."""
    schema = get_openapi_schema()
    
    for path, methods in schema["paths"].items():
        for method, details in methods.items():
            for status_code, response in details["responses"].items():
                assert "content" in response or status_code == "204", \
                    f"Missing content for {method.upper()} {path} response {status_code}"


def test_enum_values_defined():
    """Test enum values are properly defined."""
    schema = get_openapi_schema()
    
    # Health status enum
    health_response = schema["components"]["schemas"]["HealthResponse"]
    assert "enum" in health_response["properties"]["status"]
    assert "healthy" in health_response["properties"]["status"]["enum"]
    
    # RCA status enum
    rca_response = schema["components"]["schemas"]["RCAResponse"]
    assert "enum" in rca_response["properties"]["status"]
    assert "success" in rca_response["properties"]["status"]["enum"]

