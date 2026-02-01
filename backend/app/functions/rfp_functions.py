"""
Function definitions for LLM function calling.

Defines the schema for:
1. analyze_rfp - Extract requirements from RFP
2. generate_rfp_response - Generate python-docx code for the proposal
"""

ANALYZE_RFP_FUNCTION = {
    "name": "analyze_rfp",
    "description": "Analyze an RFP document and extract structured requirements, evaluation criteria, and submission requirements.",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief 2-3 sentence summary of what the RFP is requesting."
            },
            "requirements": {
                "type": "array",
                "description": "List of requirements extracted from the RFP.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique identifier like REQ-001"
                        },
                        "description": {
                            "type": "string",
                            "description": "Clear description of the requirement"
                        },
                        "category": {
                            "type": "string",
                            "enum": ["technical", "management", "cost", "experience", "compliance", "other"]
                        },
                        "is_mandatory": {
                            "type": "boolean",
                            "description": "Whether this is a mandatory requirement"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"]
                        }
                    },
                    "required": ["id", "description", "category", "is_mandatory"]
                }
            },
            "evaluation_criteria": {
                "type": "array",
                "description": "How proposals will be evaluated.",
                "items": {
                    "type": "object",
                    "properties": {
                        "criterion": {"type": "string"},
                        "weight": {"type": "number"},
                        "description": {"type": "string"}
                    },
                    "required": ["criterion"]
                }
            },
            "submission_requirements": {
                "type": "object",
                "description": "Logistics for submission.",
                "properties": {
                    "deadline": {"type": "string"},
                    "format": {"type": "string"},
                    "page_limit": {"type": "integer"},
                    "sections_required": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            "key_differentiators": {
                "type": "array",
                "description": "What would make a proposal stand out.",
                "items": {"type": "string"}
            }
        },
        "required": ["summary", "requirements"]
    }
}

GENERATE_RFP_RESPONSE_FUNCTION = {
    "name": "generate_rfp_response",
    "description": "Generate complete Python code that creates the RFP proposal Word document.",
    "parameters": {
        "type": "object",
        "properties": {
            "document_code": {
                "type": "string",
                "description": """Complete Python code that creates the full proposal Word document.

## Available Variables & Imports
The code runs in an environment with:
- `doc`: A python-docx Document instance (already created)
- `output_dir`: Path to save any generated images
- `Inches`, `Pt`, `Cm`: From docx.shared for sizing
- `WD_ALIGN_PARAGRAPH`: From docx.enum.text
- `WD_TABLE_ALIGNMENT`: From docx.enum.table
- `plt`, `sns`, `np`, `pd`: matplotlib.pyplot, seaborn, numpy, pandas
- `render_mermaid(code, filename)`: Helper to render mermaid diagrams to PNG

## Creating Charts with Seaborn
```python
# Create a chart
import matplotlib.pyplot as plt
import seaborn as sns

plt.figure(figsize=(8, 5))
sns.set_style("whitegrid")
data = {'Phase': ['Discovery', 'Design', 'Implementation', 'Testing'], 'Weeks': [2, 4, 8, 3]}
sns.barplot(x='Phase', y='Weeks', data=data, palette='Blues_d')
plt.title('Project Timeline')
plt.tight_layout()
chart_path = output_dir / 'timeline_chart.png'
plt.savefig(chart_path, dpi=150, bbox_inches='tight')
plt.close()

doc.add_picture(str(chart_path), width=Inches(5.5))
doc.add_paragraph('Figure 1: Project Timeline')
```

## Creating Mermaid Diagrams
Use the provided `render_mermaid(code, filename)` helper:
```python
mermaid_code = '''
flowchart TD
    A[Discovery] --> B[Design]
    B --> C[Implementation]
    C --> D[Testing]
    D --> E[Deployment]
'''

# Use the render_mermaid helper (handles path issues automatically)
diagram_path = render_mermaid(mermaid_code, 'workflow_diagram')
doc.add_picture(str(diagram_path), width=Inches(5))
doc.add_paragraph('Figure 2: Project Workflow')
```

MERMAID SYNTAX: Do NOT use parentheses () in node text - they break the parser. Use [square brackets] for labels.

## Document Structure
```python
# Title
doc.add_heading('Proposal Title', level=0)

# Section heading
doc.add_heading('Executive Summary', level=1)
doc.add_paragraph('Content here...')

# Bullet list
doc.add_paragraph('First point', style='List Bullet')
doc.add_paragraph('Second point', style='List Bullet')

# Table
table = doc.add_table(rows=3, cols=3)
table.style = 'Table Grid'
# ... populate cells

# Page break
doc.add_page_break()
```

Write complete, professional code. Do NOT call doc.save() - that's handled externally."""
            }
        },
        "required": ["document_code"]
    }
}


PLAN_PROPOSAL_FUNCTION = {
    "name": "plan_proposal",
    "description": "Create a detailed plan for the proposal before generating the document.",
    "parameters": {
        "type": "object",
        "properties": {
            "overview": {
                "type": "string",
                "description": "High-level overview of the proposal strategy."
            },
            "sections": {
                "type": "array",
                "description": "Planned sections for the proposal.",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Section title"
                        },
                        "summary": {
                            "type": "string",
                            "description": "High-level summary of what this section should cover"
                        },
                        "related_requirements": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Requirement IDs (e.g., REQ-001) this section addresses"
                        },
                        "rfp_pages": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "RFP page references (e.g., 'Page 5', 'Section 3.1')"
                        },
                        "suggested_diagrams": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Suggested mermaid diagrams (e.g., 'flowchart for process', 'sequence diagram for integration')"
                        },
                        "suggested_charts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Suggested seaborn charts (e.g., 'bar chart for timeline', 'pie chart for budget allocation')"
                        },
                        "suggested_tables": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Suggested tables (e.g., 'team qualifications table', 'pricing breakdown')"
                        }
                    },
                    "required": ["title", "summary"]
                }
            },
            "key_themes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key themes to emphasize throughout the proposal"
            },
            "win_strategy": {
                "type": "string",
                "description": "Strategy for winning this RFP"
            }
        },
        "required": ["overview", "sections"]
    }
}


CRITIQUE_RESPONSE_FUNCTION = {
    "name": "critique_response",
    "description": "Critique the generated proposal document code and determine if revisions are needed.",
    "parameters": {
        "type": "object",
        "properties": {
            "needs_revision": {
                "type": "boolean",
                "description": "True if the document needs revisions, False if it's acceptable"
            },
            "critique": {
                "type": "string",
                "description": "Detailed critique explaining what needs to be fixed. Required if needs_revision is True."
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "What the document does well"
            },
            "weaknesses": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Areas that need improvement"
            },
            "priority_fixes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Priority fixes that must be addressed if needs_revision is True"
            }
        },
        "required": ["needs_revision"]
    }
}


# All available functions
ALL_FUNCTIONS = [
    ANALYZE_RFP_FUNCTION,
    GENERATE_RFP_RESPONSE_FUNCTION,
    PLAN_PROPOSAL_FUNCTION,
    CRITIQUE_RESPONSE_FUNCTION,
]


def get_function_by_name(name: str) -> dict | None:
    """Get a function definition by name."""
    for func in ALL_FUNCTIONS:
        if func["name"] == name:
            return func
    return None
