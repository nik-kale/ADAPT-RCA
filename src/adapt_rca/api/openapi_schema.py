"""
OpenAPI schema definition for ADAPT-RCA API.

Defines the API specification in OpenAPI 3.0 format.
"""

OPENAPI_SCHEMA = {
    "openapi": "3.0.0",
    "info": {
        "title": "ADAPT-RCA API",
        "description": "Adaptive Diagnostic Agent for Proactive Troubleshooting - Root Cause Analyzer",
        "version": "5.0.0-alpha",
        "contact": {
            "name": "ADAPT-RCA Team",
            "url": "https://github.com/nik-kale/ADAPT-RCA"
        },
        "license": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        }
    },
    "servers": [
        {
            "url": "/api/v1",
            "description": "API v1"
        }
    ],
    "paths": {
        "/health": {
            "get": {
                "summary": "Health check",
                "description": "Check if the service is healthy and running",
                "operationId": "getHealth",
                "tags": ["monitoring"],
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/HealthResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/readiness": {
            "get": {
                "summary": "Readiness check",
                "description": "Check if the service is ready to handle requests",
                "operationId": "getReadiness",
                "tags": ["monitoring"],
                "responses": {
                    "200": {
                        "description": "Service readiness status",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ReadinessResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/version": {
            "get": {
                "summary": "Version information",
                "description": "Get service version information",
                "operationId": "getVersion",
                "tags": ["monitoring"],
                "responses": {
                    "200": {
                        "description": "Version information",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/VersionResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/rca": {
            "post": {
                "summary": "Analyze incident",
                "description": "Perform root cause analysis on incident events",
                "operationId": "analyzeIncident",
                "tags": ["analysis"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/RCARequest"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Analysis successful",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/RCAResponse"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid request",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/rca/{incident_id}": {
            "get": {
                "summary": "Get analysis status",
                "description": "Get the status of an RCA analysis",
                "operationId": "getRCAStatus",
                "tags": ["analysis"],
                "parameters": [
                    {
                        "name": "incident_id",
                        "in": "path",
                        "required": True,
                        "description": "Incident identifier",
                        "schema": {
                            "type": "string"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Status retrieved",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/StatusResponse"
                                }
                            }
                        }
                    },
                    "404": {
                        "description": "Incident not found",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "HealthResponse": {
                "type": "object",
                "required": ["status", "uptime_seconds", "service", "version"],
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["healthy", "unhealthy"]
                    },
                    "uptime_seconds": {
                        "type": "number"
                    },
                    "service": {
                        "type": "string"
                    },
                    "version": {
                        "type": "string"
                    }
                }
            },
            "ReadinessResponse": {
                "type": "object",
                "required": ["status", "checks"],
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["ready", "not_ready"]
                    },
                    "checks": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "boolean"
                        }
                    }
                }
            },
            "VersionResponse": {
                "type": "object",
                "required": ["version", "api_version", "platform"],
                "properties": {
                    "version": {
                        "type": "string"
                    },
                    "api_version": {
                        "type": "string"
                    },
                    "platform": {
                        "type": "string"
                    }
                }
            },
            "RCARequest": {
                "type": "object",
                "required": ["events"],
                "properties": {
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "object"
                        },
                        "minItems": 1
                    },
                    "incident_id": {
                        "type": "string"
                    }
                }
            },
            "RCAResponse": {
                "type": "object",
                "required": ["status", "incident_id"],
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["success", "error"]
                    },
                    "incident_id": {
                        "type": "string"
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time"
                    },
                    "summary": {
                        "type": "string"
                    },
                    "services": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "root_causes": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "error": {
                        "type": "string"
                    }
                }
            },
            "StatusResponse": {
                "type": "object",
                "required": ["incident_id", "status"],
                "properties": {
                    "incident_id": {
                        "type": "string"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "processing", "completed", "failed"]
                    },
                    "progress": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100
                    },
                    "message": {
                        "type": "string"
                    }
                }
            },
            "ErrorResponse": {
                "type": "object",
                "required": ["error"],
                "properties": {
                    "error": {
                        "type": "string"
                    },
                    "details": {
                        "type": "string"
                    }
                }
            }
        }
    }
}


def get_openapi_schema() -> dict:
    """
    Get the OpenAPI schema.
    
    Returns:
        OpenAPI schema dictionary
    """
    return OPENAPI_SCHEMA.copy()

