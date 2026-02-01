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
4. Include relevant diagrams where they add value

Use the generate_rfp_response function to structure your output.
"""

REVIEW_PROPOSAL_USER_PROMPT = """Please review the following proposal draft against the original RFP requirements.

## Original RFP Requirements:
{rfp_analysis}

## Proposal Draft:
{proposal_draft}

## Evaluation Criteria:
{evaluation_criteria}

Provide detailed feedback on:
1. Completeness - are all requirements addressed?
2. Quality - is the content clear and professional?
3. Persuasiveness - does it make a compelling case?
4. Compliance - does it meet all mandatory requirements?
5. Diagram Quality - are the Mermaid diagrams valid and useful?

List specific improvements needed.
"""

FINALIZE_PROPOSAL_USER_PROMPT = """Finalize the proposal by incorporating the review feedback and producing the polished final version.

## Proposal Draft:
{proposal_draft}

## Review Feedback:
{review_feedback}

## Style Guidelines (from examples):
{style_guidelines}

Produce the final proposal using the generate_rfp_response function. Ensure:
1. All feedback has been incorporated
2. Formatting is consistent throughout
3. Content flows logically between sections
4. All Mermaid diagrams are valid and render properly
"""
