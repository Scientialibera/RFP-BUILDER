"""
User prompt templates for the RFP Builder workflow.
These templates are filled with context at runtime.
"""

ANALYZE_RFP_USER_PROMPT = """Please analyze the following RFP document and extract all key requirements, evaluation criteria, and submission guidelines.

## RFP Document:
{rfp_content}

## Additional Context:
{additional_context}

When citing pages, use the PAGE TO CITE numbers exactly as provided in the document.

Please provide a comprehensive analysis that will help us create a winning proposal response.
"""


PLAN_PROPOSAL_USER_PROMPT = """Based on the RFP analysis, create a detailed proposal plan.

## RFP Analysis:
{rfp_analysis}

## Requirements to Address:
{requirements}

## Company Context:
{company_context}

Create a comprehensive plan that:
1. Defines all sections the proposal should have
2. Maps each section to the requirements it addresses
3. Notes relevant RFP page numbers
4. Suggests specific visualizations (mermaid diagrams, seaborn charts, tables) for each section
5. Develops a win strategy

For each section's rfp_pages, return ONLY integer page numbers from PAGE TO CITE markers.
Do NOT return section titles, labels, or free-text references.
Do NOT write Python code or pseudo-code. This step is planning only.

Use the plan_proposal function to structure your output.
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

Generate complete Python code that creates a professional Word document:
1. Address all identified requirements
2. Match the style and format of the example RFPs
3. Incorporate our company's capabilities and differentiators
4. Include visuals selectively (diagrams/charts/tables) only where they improve clarity and decision-making

Write all charts and diagrams INLINE in the code - do NOT use placeholder strings.

Use the generate_rfp_response function to return your document_code.
"""


GENERATE_WITH_PLAN_USER_PROMPT = """Based on the RFP analysis, proposal plan, and example RFPs, generate a comprehensive proposal response.

## RFP Analysis:
{rfp_analysis}

## Proposal Plan:
{proposal_plan}

## Example RFPs (for style/format reference):
{example_rfps}

## Company Context:
{company_context}

## Requirements to Address:
{requirements}

Generate complete Python code following the proposal plan structure:
1. Implement ALL sections from the plan
2. Use the plan's suggested visualizations selectively (do NOT include all suggestions)
3. Address all requirements mapped in the plan
4. Emphasize the key themes identified in the plan
5. Match the style and format of the example RFPs

Keep visual density controlled. Choose the highest-value visuals only and avoid overloading the document.

Write all charts and diagrams INLINE in the code - do NOT use placeholder strings.

Use the generate_rfp_response function to return your document_code.
"""

GENERATE_SECTIONS_CHUNKED_USER_PROMPT = """You are generating a portion of the proposal document based on the proposal plan.

## Chunk Info:
Part {part_number} of {total_parts}
Sections to generate in this part:
{sections_outline}

## RFP Analysis:
{rfp_analysis}

## Requirements to Address (for these sections):
{requirements}

## RFP Pages (for this part, with PAGE NUMBER markers):
{rfp_pages}

## Example RFPs (for style/format reference):
{example_rfps}

## Company Context:
{company_context}

Generate COMPLETE Python code that creates ONLY the sections listed for this part.
- Do NOT generate the title page or executive summary unless explicitly listed in this part.
- Do NOT include sections outside this part.
- Keep formatting consistent and enterprise-grade.

Use the generate_rfp_response function to return your document_code.
"""

GENERATE_SECTIONS_CHUNKED_WITH_CRITIQUE_USER_PROMPT = """The previous chunk code was reviewed and needs revisions. Please address the critique and regenerate ONLY the sections listed for this chunk.

## Critique:
{critique}

## Previous Code:
{previous_code}

## Chunk Info:
Part {part_number} of {total_parts}
Sections to generate in this part:
{sections_outline}

## RFP Analysis:
{rfp_analysis}

## Requirements to Address (for these sections):
{requirements}

## RFP Pages (for this part, with PAGE NUMBER markers):
{rfp_pages}

## Example RFPs (for style/format reference):
{example_rfps}

## Company Context:
{company_context}

Regenerate ONLY the sections listed for this part. Do not include sections outside this part.

Use the generate_rfp_response function to return your document_code.
"""

SYNTHESIZE_DOCUMENT_CODE_PROMPT = """You will be given multiple code chunks that each generate specific sections of a proposal document.

Your task: produce ONE cohesive, executable Python code file that:
- Includes all sections exactly once
- Preserves consistent formatting and style
- Avoids duplicates and conflicting styles
- Works as a single, complete document

## Chunk Code Inputs:
{chunk_codes}

Use the generate_rfp_response function to return the final document_code.
"""

GENERATE_WITH_ERROR_USER_PROMPT = """The previous document code failed to execute. Please fix the error and regenerate.

## Error Details:
{error_message}

## Previous Code (with error):
{previous_code}

## RFP Analysis:
{rfp_analysis}

## Requirements to Address:
{requirements}

Fix the error in the code and regenerate. Common issues:
- Mermaid syntax: Do NOT use parentheses () in node labels, use [square brackets]
- Bullet lists: Pass text as first arg: doc.add_paragraph('text', style='List Bullet')
- Charts: Always close figures with plt.close() after saving
- Paths: Use output_dir / 'filename.png' for image paths

Use the generate_rfp_response function to return your corrected document_code.
"""


GENERATE_WITH_CRITIQUE_USER_PROMPT = """The previous document code was reviewed and needs revisions. Please address the critique and regenerate.

## Critique:
{critique}

## Previous Code:
{previous_code}

## RFP Analysis:
{rfp_analysis}

## Requirements to Address:
{requirements}

Address the critique and improve the document code. Focus on:
1. Priority fixes mentioned in the critique
2. Weaknesses identified
3. Missing requirements coverage

Use the generate_rfp_response function to return your improved document_code.
"""


CRITIQUE_DOCUMENT_USER_PROMPT = """Review the following proposal document code and determine if it needs revisions.

## RFP Requirements:
{requirements}

## Generated Document Code:
{document_code}

Review the code for:
1. Completeness - does it address all requirements?
2. Technical correctness - will the code execute successfully?
3. Professional quality - is it well-structured and compelling?
4. Visualization quality - are diagrams/charts appropriate and correct?

Use the critique_response function to provide your assessment.
"""
