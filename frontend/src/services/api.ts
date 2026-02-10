/**
 * API client for RFP Builder backend.
 */

import axios from 'axios';
import type {
  ConfigResponse,
  CritiqueStepRequest,
  CritiqueStepResponse,
  ExtractReqsResponse,
  GenerateRFPResponse,
  GenerateRFPStepResponse,
  HealthResponse,
  PlanStepRequest,
  PlanStepResponse,
  PromptDefinition,
  PromptUpdateRequest,
  PromptsResponse,
  ProposalPlan,
  RFPAnalysis,
  RunsListResponse,
  RunCodeResponse,
  RunWorkflowStateResponse,
  RunDetails,
  RegenerateResponse,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 600000,
});

export async function getHealth(): Promise<HealthResponse> {
  const response = await axios.get<HealthResponse>(`${API_BASE}/health`);
  return response.data;
}

export async function getConfig(): Promise<ConfigResponse> {
  const response = await api.get<ConfigResponse>('/config');
  return response.data;
}

export async function getPrompts(
  adminPermission?: string,
  userRoles?: string[]
): Promise<PromptsResponse> {
  const params: Record<string, string> = {};
  if (adminPermission?.trim()) {
    params.admin_permission = adminPermission.trim();
  }
  if (userRoles && userRoles.length > 0) {
    params.user_roles = userRoles.join(',');
  }
  const response = await api.get<PromptsResponse>('/config/prompts', {
    params: Object.keys(params).length > 0 ? params : undefined,
  });
  return response.data;
}

export async function updatePrompt(request: PromptUpdateRequest): Promise<PromptDefinition> {
  const response = await api.put<PromptDefinition>('/config/prompts', request);
  return response.data;
}

export interface GenerateOptions {
  enablePlanner?: boolean;
  enableCritiquer?: boolean;
}

export async function generateRFP(
  rfp: File,
  exampleRfps: File[],
  companyContext?: File[]
): Promise<GenerateRFPResponse> {
  const formData = new FormData();
  formData.append('source_rfp', rfp);
  exampleRfps.forEach((file) => formData.append('example_rfps', file));
  companyContext?.forEach((file) => formData.append('company_context', file));

  const response = await api.post<GenerateRFPResponse>('/rfp/orchestrate', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function generateRFPStream(
  rfp: File,
  exampleRfps: File[],
  companyContext: File[] | undefined,
  onEvent: (event: { event: string; step?: string; message?: string; data?: Record<string, unknown> }) => void,
  options?: GenerateOptions
): Promise<void> {
  const formData = new FormData();
  formData.append('source_rfp', rfp);
  exampleRfps.forEach((file) => formData.append('example_rfps', file));
  companyContext?.forEach((file) => formData.append('company_context', file));

  if (options?.enablePlanner !== undefined) {
    formData.append('enable_planner', options.enablePlanner.toString());
  }
  if (options?.enableCritiquer !== undefined) {
    formData.append('enable_critiquer', options.enableCritiquer.toString());
  }

  const response = await fetch(`${API_BASE}/rfp/orchestrate/stream`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split('\n');
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const data = JSON.parse(line.slice(6));
        onEvent(data);
      } catch {
        // Ignore malformed SSE frames
      }
    }
  }
}

export async function extractReqs(
  sourceRfp: File,
  companyContext: File[] | undefined,
  comment?: string,
  previousRequirements?: RFPAnalysis['requirements'],
  runId?: string
): Promise<ExtractReqsResponse> {
  const formData = new FormData();
  formData.append('source_rfp', sourceRfp);
  companyContext?.forEach((file) => formData.append('company_context', file));
  if (comment?.trim()) {
    formData.append('comment', comment.trim());
  }
  if (previousRequirements && previousRequirements.length > 0) {
    formData.append('previous_requirements', JSON.stringify(previousRequirements));
  }
  if (runId?.trim()) {
    formData.append('run_id', runId.trim());
  }

  const response = await api.post<ExtractReqsResponse>('/rfp/extract-reqs', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function planProposal(request: PlanStepRequest): Promise<PlanStepResponse> {
  const response = await api.post<PlanStepResponse>('/rfp/plan', request);
  return response.data;
}

export interface PlanWithContextParams {
  analysis: RFPAnalysis;
  companyContextText?: string;
  companyContextFiles?: File[];
  comment?: string;
  previousPlan?: ProposalPlan;
  runId?: string;
}

export async function planProposalWithContext(params: PlanWithContextParams): Promise<PlanStepResponse> {
  const formData = new FormData();
  formData.append('analysis_json', JSON.stringify(params.analysis));
  if (params.companyContextText?.trim()) {
    formData.append('company_context_text', params.companyContextText.trim());
  }
  params.companyContextFiles?.forEach((file) => formData.append('company_context', file));
  if (params.comment?.trim()) {
    formData.append('comment', params.comment.trim());
  }
  if (params.previousPlan) {
    formData.append('previous_plan_json', JSON.stringify(params.previousPlan));
  }
  if (params.runId?.trim()) {
    formData.append('run_id', params.runId.trim());
  }

  const response = await api.post<PlanStepResponse>('/rfp/plan-with-context', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export interface GenerateCustomRFPParams {
  sourceRfp: File;
  exampleRfps: File[];
  companyContext?: File[];
  analysis: RFPAnalysis;
  plan?: ProposalPlan;
  comment?: string;
  previousDocumentCode?: string;
  generatorFormattingInjection?: string;
  generatorIntroPages?: number;
  generationPageOverlap?: number;
  toggleGenerationChunking?: boolean;
  maxTokensGenerationChunking?: number;
  maxSectionsPerChunk?: number;
  runId?: string;
}

export async function generateCustomRFP(params: GenerateCustomRFPParams): Promise<GenerateRFPStepResponse> {
  const formData = new FormData();
  formData.append('source_rfp', params.sourceRfp);
  params.exampleRfps.forEach((file) => formData.append('example_rfps', file));
  params.companyContext?.forEach((file) => formData.append('company_context', file));
  formData.append('analysis_json', JSON.stringify(params.analysis));

  if (params.plan) {
    formData.append('plan_json', JSON.stringify(params.plan));
  }
  if (params.comment?.trim()) {
    formData.append('comment', params.comment.trim());
  }
  if (params.previousDocumentCode?.trim()) {
    formData.append('previous_document_code', params.previousDocumentCode);
  }
  if (params.generatorFormattingInjection) {
    formData.append('generator_formatting_injection', params.generatorFormattingInjection);
  }
  if (params.generatorIntroPages !== undefined) {
    formData.append('generator_intro_pages', String(params.generatorIntroPages));
  }
  if (params.generationPageOverlap !== undefined) {
    formData.append('generation_page_overlap', String(params.generationPageOverlap));
  }
  if (params.toggleGenerationChunking !== undefined) {
    formData.append('toggle_generation_chunking', String(params.toggleGenerationChunking));
  }
  if (params.maxTokensGenerationChunking !== undefined) {
    formData.append('max_tokens_generation_chunking', String(params.maxTokensGenerationChunking));
  }
  if (params.maxSectionsPerChunk !== undefined) {
    formData.append('max_sections_per_chunk', String(params.maxSectionsPerChunk));
  }
  if (params.runId?.trim()) {
    formData.append('run_id', params.runId.trim());
  }

  const response = await api.post<GenerateRFPStepResponse>('/rfp/generate-rfp', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function critiqueRFP(request: CritiqueStepRequest): Promise<CritiqueStepResponse> {
  const response = await api.post<CritiqueStepResponse>('/rfp/critique', request);
  return response.data;
}

export function getDownloadUrl(path: string): string {
  return `${API_BASE}${path}`;
}

// ============================================================================
// Runs API
// ============================================================================

export async function listRuns(limit = 50, offset = 0): Promise<RunsListResponse> {
  const response = await api.get<RunsListResponse>('/runs', {
    params: { limit, offset },
  });
  return response.data;
}

export async function getRunDetails(runId: string): Promise<RunDetails> {
  const response = await api.get<RunDetails>(`/runs/${runId}`);
  return response.data;
}

export async function getRunCode(runId: string, stage = '99_final'): Promise<RunCodeResponse> {
  const response = await api.get<RunCodeResponse>(`/runs/${runId}/code`, {
    params: { stage },
  });
  return response.data;
}

export async function getRunWorkflowState(runId: string): Promise<RunWorkflowStateResponse> {
  const response = await api.get<RunWorkflowStateResponse>(`/runs/${runId}/workflow-state`);
  return response.data;
}

export async function regenerateDocument(runId: string, code: string): Promise<RegenerateResponse> {
  const response = await api.post<RegenerateResponse>(`/runs/${runId}/regenerate`, { code });
  return response.data;
}

export function getSourceDocumentUrl(runId: string, filename: string): string {
  return `${API_BASE}/runs/${runId}/documents/${encodeURIComponent(filename)}`;
}

export function getRevisionDownloadUrl(runId: string, revisionId: string, filename: string): string {
  return `${API_BASE}/runs/${runId}/revisions/${revisionId}/${encodeURIComponent(filename)}`;
}

export default api;
