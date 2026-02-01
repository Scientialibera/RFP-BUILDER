"""
User prompt templates for the RFP Builder workflow.
These templates are filled with context at runtime.
"""

ANALYZE_RFP_USER_PROMPT = """Please analyze the following RFP document and extract all key requirements, evaluation criteria, and submission guidelines.

## RFP Document:
{rfp_content}

## Additional Context:
{additional_context}

Please provide a comprehensive analysis that will help us create a winning proposal response.
"""

GENERATE_SECTIONS_USER_PROMPT = """Based on the RFP analysis and example RFPs provided, generate a comprehensive proposal response.

## RFP Analysis:
{rfp_analysis}

## Example RFPs (for style/format reference):
{example_rfps}

## Company Context:
{company_context}

## Requirements to Address:
{requirements}

Generate well-structured proposal sections that:
1. Address all identified requirements
2. Match the style and format of the example RFPs
3. Incorporate our company's capabilities and differentiators
4. MUST include at least 2-3 Mermaid diagrams AND 1-2 Python charts AND 1-2 tables

REMEMBER: Use placeholders ({{MERMAID_DIAGRAM_1}}, {{PYTHON_CHART_1}}, {{TABLE_1}}) in content and provide code in the function parameters.

Use the generate_rfp_response function to structure your output.
"""
