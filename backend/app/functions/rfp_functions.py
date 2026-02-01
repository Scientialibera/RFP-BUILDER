"""
RFP-specific function definitions for LLM function calling.
These define the structured output formats the LLM should use.
"""

from typing import Any

# Main function for generating the final RFP response
GENERATE_RFP_RESPONSE_FUNCTION: dict[str, Any] = {
    "name": "generate_rfp_response",
    "description": "Generate a structured RFP response with properly formatted sections. Use this function to output the final proposal content.",
    "parameters": {
        "type": "object",
        "properties": {
            "sections": {
                "type": "array",
                "description": "Array of proposal sections in order. Each section has a title, content, and type.",
                "items": {
                    "type": "object",
                    "properties": {
                        "section_title": {
                            "type": "string",
                            "description": "The title of this section (e.g., 'Executive Summary', 'Technical Approach')"
                        },
                        "section_content": {
                            "type": "string",
                            "description": "The content of this section. Can include Markdown formatting and Mermaid diagrams wrapped in ```mermaid blocks."
                        },
                        "section_type": {
                            "type": "string",
                            "enum": ["h1", "h2", "h3", "body"],
                            "description": "The type of section: h1 for main headers, h2 for sub-headers, h3 for sub-sub-headers, body for content paragraphs"
                        }
                    },
                    "required": ["section_title", "section_content", "section_type"]
                }
            },
            "metadata": {
                "type": "object",
                "description": "Optional metadata about the response",
                "properties": {
                    "total_sections": {
                        "type": "integer",
                        "description": "Total number of sections generated"
                    },
                    "has_diagrams": {
                        "type": "boolean",
                        "description": "Whether the response contains Mermaid diagrams"
                    },
                    "estimated_pages": {
                        "type": "integer",
                        "description": "Estimated number of pages when formatted"
                    }
                }
            }
        },
        "required": ["sections"]
    }
}

# Function for analyzing RFP requirements
ANALYZE_RFP_FUNCTION: dict[str, Any] = {
    "name": "analyze_rfp",
    "description": "Analyze an RFP document and extract structured requirements and criteria.",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of what the RFP is requesting"
            },
            "requirements": {
                "type": "array",
                "description": "List of requirements extracted from the RFP",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique identifier for this requirement (e.g., REQ-001)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Full description of the requirement"
                        },
                        "category": {
                            "type": "string",
                            "enum": ["technical", "management", "cost", "experience", "compliance", "other"],
                            "description": "Category of the requirement"
                        },
                        "is_mandatory": {
                            "type": "boolean",
                            "description": "Whether this requirement is mandatory for compliance"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Relative priority/weight of this requirement"
                        }
                    },
                    "required": ["id", "description", "category", "is_mandatory"]
                }
            },
            "evaluation_criteria": {
                "type": "array",
                "description": "Evaluation criteria and scoring methodology",
                "items": {
                    "type": "object",
                    "properties": {
                        "criterion": {
                            "type": "string",
                            "description": "Name of the evaluation criterion"
                        },
                        "weight": {
                            "type": "number",
                            "description": "Weight or points for this criterion (if specified)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of what evaluators are looking for"
                        }
                    },
                    "required": ["criterion"]
                }
            },
            "submission_requirements": {
                "type": "object",
                "description": "Submission logistics and requirements",
                "properties": {
                    "deadline": {
                        "type": "string",
                        "description": "Submission deadline if specified"
                    },
                    "format": {
                        "type": "string",
                        "description": "Required format (e.g., PDF, Word)"
                    },
                    "page_limit": {
                        "type": "integer",
                        "description": "Maximum page count if specified"
                    },
                    "sections_required": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of required sections"
                    }
                }
            },
            "key_differentiators": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key areas where we can differentiate our proposal"
            }
        },
        "required": ["summary", "requirements"]
    }
}

# Review feedback function
REVIEW_PROPOSAL_FUNCTION: dict[str, Any] = {
    "name": "review_proposal",
    "description": "Provide structured review feedback on a proposal draft.",
    "parameters": {
        "type": "object",
        "properties": {
            "overall_score": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Overall quality score from 1-10"
            },
            "compliance_status": {
                "type": "string",
                "enum": ["compliant", "partially_compliant", "non_compliant"],
                "description": "Whether the proposal meets mandatory requirements"
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of proposal strengths"
            },
            "weaknesses": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of proposal weaknesses"
            },
            "required_changes": {
                "type": "array",
                "description": "Changes that must be made",
                "items": {
                    "type": "object",
                    "properties": {
                        "section": {
                            "type": "string",
                            "description": "Which section needs changes"
                        },
                        "issue": {
                            "type": "string",
                            "description": "Description of the issue"
                        },
                        "suggestion": {
                            "type": "string",
                            "description": "Suggested fix"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["critical", "important", "nice_to_have"]
                        }
                    },
                    "required": ["section", "issue", "suggestion"]
                }
            },
            "missing_requirements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Requirements from the RFP that aren't addressed"
            }
        },
        "required": ["overall_score", "compliance_status", "required_changes"]
    }
}

# Collection of all functions
ALL_FUNCTIONS: list[dict[str, Any]] = [
    GENERATE_RFP_RESPONSE_FUNCTION,
    ANALYZE_RFP_FUNCTION,
    REVIEW_PROPOSAL_FUNCTION,
]


def get_function_by_name(name: str) -> dict[str, Any] | None:
    """Get a function definition by its name."""
    for func in ALL_FUNCTIONS:
        if func["name"] == name:
            return func
    return None
