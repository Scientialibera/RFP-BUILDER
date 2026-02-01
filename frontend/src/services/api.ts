/**
 * API client for RFP Builder backend
 */

import axios from 'axios';
import type { GenerateRFPResponse, HealthResponse, ConfigResponse } from '../types';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 300000, // 5 minutes for long-running requests
});

/**
 * Health check
 */
export async function getHealth(): Promise<HealthResponse> {
  const response = await axios.get<HealthResponse>('/health');
  return response.data;
}

/**
 * Get frontend configuration
 */
export async function getConfig(): Promise<ConfigResponse> {
  const response = await api.get<ConfigResponse>('/config');
  return response.data;
}

/**
 * Generate RFP response
 */
export async function generateRFP(
  rfp: File,
  exampleRfps: File[],
  companyContext?: File[]
): Promise<GenerateRFPResponse> {
  const formData = new FormData();
  
  formData.append('rfp', rfp);
  
  exampleRfps.forEach((file) => {
    formData.append('example_rfps', file);
  });
  
  if (companyContext) {
    companyContext.forEach((file) => {
      formData.append('company_context', file);
    });
  }
  
  const response = await api.post<GenerateRFPResponse>('/rfp/generate', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
}

/**
 * Generate RFP with streaming events
 */
export async function generateRFPStream(
  rfp: File,
  exampleRfps: File[],
  companyContext: File[] | undefined,
  onEvent: (event: { event: string; step?: string; message?: string; data?: Record<string, unknown> }) => void
): Promise<void> {
  const formData = new FormData();
  
  formData.append('rfp', rfp);
  
  exampleRfps.forEach((file) => {
    formData.append('example_rfps', file);
  });
  
  if (companyContext) {
    companyContext.forEach((file) => {
      formData.append('company_context', file);
    });
  }
  
  const response = await fetch(`${API_BASE}/rfp/generate/stream`, {
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
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          onEvent(data);
        } catch {
          // Ignore parse errors
        }
      }
    }
  }
}

/**
 * Download generated PDF
 */
export function getDownloadUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export default api;
