/**
 * API types matching backend schemas.
 */

export interface RFPResponse {
  document_code: string;
}

export interface RFPRequirement {
  id: string;
  description: string;
  category: 'technical' | 'management' | 'cost' | 'experience' | 'compliance' | 'other';
  is_mandatory: boolean;
  priority?: 'high' | 'medium' | 'low';
}

export interface EvaluationCriterion {
  criterion: string;
  weight?: number;
  description?: string;
}

export interface SubmissionRequirements {
  deadline?: string;
  format?: string;
  page_limit?: number;
  sections_required?: string[];
}

export interface RFPAnalysis {
  summary: string;
  requirements: RFPRequirement[];
  evaluation_criteria?: EvaluationCriterion[];
  submission_requirements?: SubmissionRequirements;
  key_differentiators?: string[];
}

export interface PlannedSection {
  title: string;
  summary: string;
  related_requirements: string[];
  rfp_pages: number[];
  suggested_diagrams: string[];
  suggested_charts: string[];
  suggested_tables: string[];
}

export interface ProposalPlan {
  overview: string;
  sections: PlannedSection[];
  key_themes: string[];
  win_strategy: string;
}

export interface CritiqueResult {
  needs_revision: boolean;
  critique: string;
  strengths: string[];
  weaknesses: string[];
  priority_fixes: string[];
}

export interface GenerateRFPResponse {
  success: boolean;
  message: string;
  rfp_response?: RFPResponse;
  analysis?: RFPAnalysis;
  docx_download_url?: string;
  processing_time_seconds?: number;
}

export interface ExtractReqsResponse {
  success: boolean;
  message: string;
  analysis?: RFPAnalysis;
}

export interface PlanStepRequest {
  analysis: RFPAnalysis;
  company_context_text?: string;
  comment?: string;
  previous_plan?: ProposalPlan;
}

export interface PlanStepResponse {
  success: boolean;
  message: string;
  plan?: ProposalPlan;
}

export interface GenerateRFPStepResponse {
  success: boolean;
  message: string;
  document_code: string;
  docx_base64: string;
  docx_filename: string;
  docx_content_type: string;
  execution_stats: Record<string, unknown>;
  run_id?: string;
  docx_download_url?: string;
}

export interface CritiqueStepRequest {
  analysis: RFPAnalysis;
  document_code: string;
  comment?: string;
}

export interface CritiqueStepResponse {
  success: boolean;
  message: string;
  critique?: CritiqueResult;
}

export interface HealthResponse {
  status: string;
  version: string;
  llm_configured: boolean;
  auth_enabled: boolean;
  images_enabled: boolean;
}

export interface WorkflowStepConfig {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
}

export interface ConfigResponse {
  auth_enabled: boolean;
  images_enabled: boolean;
  enable_planner: boolean;
  enable_critiquer: boolean;
  workflow_steps: WorkflowStepConfig[];
  msal_client_id?: string;
  msal_tenant_id?: string;
  msal_redirect_uri?: string;
  msal_scopes?: string[];
}

export interface PromptDefinition {
  name: string;
  content: string;
}

export interface PromptsResponse {
  system_prompts: PromptDefinition[];
  base_prompts: PromptDefinition[];
}

export interface WorkflowEvent {
  event: string;
  step?: string;
  message?: string;
  data?: Record<string, unknown>;
}

// ============================================================================
// Runs API Types
// ============================================================================

export interface DocumentSummary {
  filename: string;
  file_type: 'rfp' | 'example' | 'context' | 'unknown';
}

export interface RevisionInfo {
  revision_id: string;
  created_at: string;
  docx_filename: string;
}

export interface RunSummary {
  run_id: string;
  created_at: string;
  has_docx: boolean;
  has_plan: boolean;
  critique_count: number;
  revision_count: number;
}

export interface RunDetails {
  run_id: string;
  created_at: string;
  has_docx: boolean;
  has_plan: boolean;
  critique_count: number;
  documents: DocumentSummary[];
  revisions: RevisionInfo[];
  docx_download_url?: string;
  code_available: boolean;
}

export interface RunCodeResponse {
  run_id: string;
  code: string;
  stage: string;
}

export interface RunsListResponse {
  runs: RunSummary[];
  total: number;
}

export interface RegenerateResponse {
  success: boolean;
  message: string;
  revision_id: string;
  docx_download_url: string;
}
