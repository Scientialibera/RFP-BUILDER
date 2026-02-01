/**
 * API types matching the backend schemas
 */

export interface RFPSection {
  section_title: string;
  section_content: string;
  section_type: 'h1' | 'h2' | 'h3' | 'body';
}

export interface RFPResponseMetadata {
  total_sections?: number;
  has_diagrams?: boolean;
  estimated_pages?: number;
}

export interface RFPResponse {
  sections: RFPSection[];
  metadata?: RFPResponseMetadata;
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

export interface GenerateRFPResponse {
  success: boolean;
  message: string;
  rfp_response?: RFPResponse;
  analysis?: RFPAnalysis;
  pdf_download_url?: string;
  docx_download_url?: string;
  processing_time_seconds?: number;
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
