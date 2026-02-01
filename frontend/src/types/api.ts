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
  processing_time_seconds?: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  llm_configured: boolean;
  auth_enabled: boolean;
  images_enabled: boolean;
}

export interface ConfigResponse {
  auth_enabled: boolean;
  images_enabled: boolean;
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
