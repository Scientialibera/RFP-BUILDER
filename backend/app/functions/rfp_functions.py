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
- `subprocess`, `tempfile`, `os`: For running mermaid CLI

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
```python
import subprocess
import tempfile

mermaid_code = '''
flowchart TD
    A[Discovery] --> B[Design]
    B --> C[Implementation]
    C --> D[Testing]
    D --> E[Deployment]
'''

# Save mermaid code to temp file
with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
    f.write(mermaid_code)
    mmd_path = f.name

diagram_path = output_dir / 'workflow_diagram.png'
subprocess.run(['mmdc', '-i', mmd_path, '-o', str(diagram_path), '-b', 'transparent'], check=True)

doc.add_picture(str(diagram_path), width=Inches(5))
doc.add_paragraph('Figure 2: Project Workflow')
```

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

# All available functions
ALL_FUNCTIONS = [
    ANALYZE_RFP_FUNCTION,
    GENERATE_RFP_RESPONSE_FUNCTION,
]


def get_function_by_name(name: str) -> dict | None:
    """Get a function definition by name."""
    for func in ALL_FUNCTIONS:
        if func["name"] == name:
            return func
    return None
