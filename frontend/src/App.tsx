/**
 * Main Application Component
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Send, Loader, AlertCircle, RefreshCw, Download, History } from 'lucide-react';
import { Header, FileUpload, ProgressSteps, ResponseViewer, CustomFlow, PromptsViewer } from './components';
import { RunsHistory } from './components/RunsHistory';
import { generateRFPStream, getConfig, getPrompts, updatePrompt } from './services/api';
import type { GenerateRFPResponse, ConfigResponse, WorkflowStepConfig, PromptsResponse } from './types';
import { useAuth } from './context/AuthContext';

// Default steps shown while config loads
const DEFAULT_WORKFLOW_STEPS: WorkflowStepConfig[] = [
  { id: 'upload', name: 'Upload Documents', description: 'Preparing your files', enabled: true },
  { id: 'analyze', name: 'Analyze RFP', description: 'Extracting requirements', enabled: true },
  { id: 'generate', name: 'Generate Sections', description: 'Creating proposal content', enabled: true },
  { id: 'execute_code', name: 'Execute Code', description: 'Generating diagrams, charts & tables', enabled: true },
  { id: 'complete', name: 'Complete', description: 'Document ready for download', enabled: true },
];

function App() {
  const { roles, hasRole } = useAuth();

  // Config state
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  
  // Form state
  const [rfpFile, setRfpFile] = useState<File[]>([]);
  const [exampleFiles, setExampleFiles] = useState<File[]>([]);
  const [contextFiles, setContextFiles] = useState<File[]>([]);
  
  // Feature toggles (initialized from config, can be overridden by user)
  const [enablePlanner, setEnablePlanner] = useState<boolean | null>(null);
  const [enableCritiquer, setEnableCritiquer] = useState<boolean | null>(null);

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [connectionLost, setConnectionLost] = useState(false);

  // Result state
  const [result, setResult] = useState<GenerateRFPResponse | null>(null);
  
  // Runs history modal state
  const [showRunsHistory, setShowRunsHistory] = useState(false);
  const [activeTab, setActiveTab] = useState<'standard' | 'custom' | 'config'>('standard');
  const [customFlowLoadRequest, setCustomFlowLoadRequest] = useState<{ runId: string; nonce: number } | null>(null);
  const [prompts, setPrompts] = useState<PromptsResponse | null>(null);
  const [promptsLoading, setPromptsLoading] = useState(false);
  const [promptsError, setPromptsError] = useState<string | null>(null);

  const requiredFrontEndRole = config?.front_end_required_role?.trim() || '';
  const hasRequiredFrontEndRole = hasRole(requiredFrontEndRole || undefined);
  const canAccessPrompts =
    !(config?.front_end_auth ?? false) || hasRequiredFrontEndRole;
  
  // Effective values (user override or config default)
  const effectivePlanner = enablePlanner ?? config?.enable_planner ?? false;
  const effectiveCritiquer = enableCritiquer ?? config?.enable_critiquer ?? false;

  // Get workflow steps from config (filter to enabled only)
  const workflowSteps = (config?.workflow_steps ?? DEFAULT_WORKFLOW_STEPS)
    .filter(step => step.enabled);

  // Load config on mount
  const loadConfig = useCallback(async () => {
    try {
      const configData = await getConfig();
      setConfig(configData);
      setConnectionLost(false);
    } catch (err) {
      console.error('Failed to load config:', err);
      setConnectionLost(true);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const loadPrompts = useCallback(async () => {
    setPromptsLoading(true);
    setPromptsError(null);
    try {
      const data = await getPrompts(undefined, roles);
      setPrompts(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load prompts';
      setPromptsError(message);
    } finally {
      setPromptsLoading(false);
    }
  }, [roles]);

  const handleSavePrompt = useCallback(
    async (promptGroup: 'system' | 'base', promptName: string, content: string) => {
      const updated = await updatePrompt({
        prompt_group: promptGroup,
        prompt_name: promptName,
        content,
        user_roles: roles.length > 0 ? roles : undefined,
      });

      setPrompts((prev) => {
        if (!prev) return prev;
        if (promptGroup === 'system') {
          return {
            ...prev,
            system_prompts: prev.system_prompts.map((prompt) =>
              prompt.name === updated.name ? { ...prompt, content: updated.content } : prompt
            ),
          };
        }
        return {
          ...prev,
          base_prompts: prev.base_prompts.map((prompt) =>
            prompt.name === updated.name ? { ...prompt, content: updated.content } : prompt
          ),
        };
      });
      setPromptsError(null);
    },
    [roles]
  );

  useEffect(() => {
    if (activeTab === 'config' && !prompts && !promptsLoading) {
      if (!canAccessPrompts) {
        const message = requiredFrontEndRole
          ? `Prompt access requires role "${requiredFrontEndRole}" or valid admin_permission.`
          : 'Prompt access requires valid admin_permission.';
        setPromptsError(message);
        return;
      }
      loadPrompts();
    }
  }, [activeTab, prompts, promptsLoading, loadPrompts, canAccessPrompts, requiredFrontEndRole]);

  // Auto-reload on connection lost
  const handleReload = useCallback(() => {
    window.location.reload();
  }, []);

  const canSubmit = rfpFile.length > 0 && exampleFiles.length > 0 && !isProcessing && !connectionLost;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setIsProcessing(true);
    setError(null);
    setResult(null);
    setCurrentStep('upload');
    setCompletedSteps([]);
    setConnectionLost(false);

    try {
      // Mark upload as done
      setCompletedSteps(['upload']);
      
      let downloadUrl: string | undefined;
      
      await generateRFPStream(
        rfpFile[0],
        exampleFiles,
        contextFiles.length > 0 ? contextFiles : undefined,
        (event) => {
          // Map backend step events to frontend steps
          if (event.step) {
            const stepId = event.step.toLowerCase().replace(/ /g, '_');
            
            // Mark previous steps as completed and set current
            const stepIndex = workflowSteps.findIndex(s => s.id === stepId);
            if (stepIndex >= 0) {
              const completed = workflowSteps.slice(0, stepIndex).map(s => s.id);
              setCompletedSteps(completed);
              setCurrentStep(stepId);
            }
          }
          
          // Handle completion
          if (event.event === 'complete' && event.data?.download_url) {
            downloadUrl = event.data.download_url as string;
          }
          if (event.event === 'complete' && !event.data?.download_url && (event as { download_url?: string }).download_url) {
            downloadUrl = (event as { download_url?: string }).download_url;
          }
          
          // Handle errors
          if (event.event === 'error') {
            throw new Error(event.message || 'An error occurred during generation');
          }
        },
        {
          enablePlanner: effectivePlanner,
          enableCritiquer: effectiveCritiquer,
        }
      );

      // Mark all steps complete
      setCompletedSteps(workflowSteps.map(s => s.id));
      setCurrentStep(null);
      
      setResult({
        success: true,
        message: 'RFP response generated successfully',
        docx_download_url: downloadUrl,
      });
    } catch (err) {
      console.error('Generation failed:', err);
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
      
      // Check if it's a connection error
      if (errorMessage.includes('fetch') || errorMessage.includes('network') || errorMessage.includes('Failed to fetch')) {
        setConnectionLost(true);
        setError('Connection to server lost. Please reload the page.');
      } else {
        setError(errorMessage);
      }
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReset = () => {
    setRfpFile([]);
    setExampleFiles([]);
    setContextFiles([]);
    setResult(null);
    setError(null);
    setCurrentStep(null);
    setCompletedSteps([]);
    setConnectionLost(false);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Title */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">RFP Response Generator</h1>
          <p className="mt-2 text-lg text-gray-600">
            Upload your RFP and examples to generate a professional proposal response
          </p>
          <button
            onClick={() => setShowRunsHistory(true)}
            className="mt-4 inline-flex items-center px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg border border-gray-300 transition-colors"
          >
            <History className="h-4 w-4 mr-2" />
            View Past Runs
          </button>
        </div>

        {/* Runs History Modal */}
        {showRunsHistory && (
          <RunsHistory
            onClose={() => setShowRunsHistory(false)}
            onLoadToCustomFlow={(runId) => {
              setCustomFlowLoadRequest({ runId, nonce: Date.now() });
              setActiveTab('custom');
              setShowRunsHistory(false);
            }}
          />
        )}

        <div className="mb-6 inline-flex rounded-lg border border-gray-200 bg-white p-1">
          <button
            type="button"
            onClick={() => setActiveTab('standard')}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              activeTab === 'standard'
                ? 'bg-primary-600 text-white'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
            }`}
          >
            Standard Flow
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('custom')}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              activeTab === 'custom'
                ? 'bg-primary-600 text-white'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
            }`}
          >
            Custom Flow
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('config')}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              activeTab === 'config'
                ? 'bg-primary-600 text-white'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
            }`}
          >
            Config
          </button>
        </div>

        {activeTab === 'standard' && (!result ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Form */}
            <div className="lg:col-span-2">
              <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm p-6 space-y-6">
                {/* RFP to respond to */}
                <FileUpload
                  label="RFP Document"
                  description="The RFP you want to respond to"
                  files={rfpFile}
                  onFilesChange={setRfpFile}
                  multiple={false}
                  required
                />

                {/* Example RFPs */}
                <FileUpload
                  label="Example RFP Responses"
                  description="Previous RFP responses to use as style references"
                  files={exampleFiles}
                  onFilesChange={setExampleFiles}
                  multiple
                  maxFiles={5}
                  required
                />

                {/* Company Context */}
                <FileUpload
                  label="Company Context (Optional)"
                  description="Documents about your company's capabilities, case studies, etc."
                  files={contextFiles}
                  onFilesChange={setContextFiles}
                  multiple
                  maxFiles={5}
                />

                {/* Error */}
                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
                    <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 mr-3 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="font-medium text-red-800">Generation Failed</p>
                      <p className="text-sm text-red-700 mt-1">{error}</p>
                      {connectionLost && (
                        <button
                          type="button"
                          onClick={handleReload}
                          className="mt-3 inline-flex items-center px-3 py-1.5 bg-red-600 text-white text-sm font-medium rounded hover:bg-red-700 transition-colors"
                        >
                          <RefreshCw className="h-4 w-4 mr-1.5" />
                          Reload Page
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {/* Connection Lost Banner */}
                {connectionLost && !error && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-center justify-between">
                    <div className="flex items-center">
                      <AlertCircle className="h-5 w-5 text-yellow-500 mr-3" />
                      <p className="text-sm text-yellow-800">Connection to server lost</p>
                    </div>
                    <button
                      type="button"
                      onClick={handleReload}
                      className="inline-flex items-center px-3 py-1.5 bg-yellow-600 text-white text-sm font-medium rounded hover:bg-yellow-700 transition-colors"
                    >
                      <RefreshCw className="h-4 w-4 mr-1.5" />
                      Reload
                    </button>
                  </div>
                )}

                {/* Submit */}
                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="w-full inline-flex items-center justify-center px-6 py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  {isProcessing ? (
                    <>
                      <Loader className="h-5 w-5 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Send className="h-5 w-5 mr-2" />
                      Generate RFP Response
                    </>
                  )}
                </button>
              </form>
            </div>

            {/* Progress */}
            <div className="lg:col-span-1">
              <div className="bg-white rounded-xl shadow-sm p-6">
                <h3 className="font-semibold text-gray-900 mb-4">Generation Progress</h3>
                <ProgressSteps
                  steps={workflowSteps}
                  currentStep={currentStep}
                  completedSteps={completedSteps}
                />
                
                {/* Workflow mode indicator */}
                {config && (
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <p className="text-xs text-gray-500 mb-3">Workflow Options:</p>
                    <div className="space-y-3">
                      {/* Planner Toggle */}
                      <label className="flex items-center justify-between cursor-pointer">
                        <div className="flex items-center">
                          <span className="text-sm font-medium text-gray-700">Planner</span>
                          <span className="ml-1 text-xs text-gray-400">(sections & strategy)</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => setEnablePlanner(!effectivePlanner)}
                          disabled={isProcessing}
                          className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                            effectivePlanner ? 'bg-purple-600' : 'bg-gray-200'
                          }`}
                        >
                          <span
                            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                              effectivePlanner ? 'translate-x-5' : 'translate-x-0'
                            }`}
                          />
                        </button>
                      </label>

                      {/* Critiquer Toggle */}
                      <label className="flex items-center justify-between cursor-pointer">
                        <div className="flex items-center">
                          <span className="text-sm font-medium text-gray-700">Quality Review</span>
                          <span className="ml-1 text-xs text-gray-400">(critique & revise)</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => setEnableCritiquer(!effectiveCritiquer)}
                          disabled={isProcessing}
                          className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                            effectiveCritiquer ? 'bg-blue-600' : 'bg-gray-200'
                          }`}
                        >
                          <span
                            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                              effectiveCritiquer ? 'translate-x-5' : 'translate-x-0'
                            }`}
                          />
                        </button>
                      </label>
                    </div>
                    
                    {/* Reset to defaults hint */}
                    {(enablePlanner !== null || enableCritiquer !== null) && (
                      <button
                        type="button"
                        onClick={() => { setEnablePlanner(null); setEnableCritiquer(null); }}
                        className="mt-2 text-xs text-gray-400 hover:text-gray-600"
                      >
                        Reset to server defaults
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Tips */}
              <div className="mt-6 bg-blue-50 rounded-xl p-6">
                <h3 className="font-semibold text-blue-900 mb-3">Tips for Best Results</h3>
                <ul className="space-y-2 text-sm text-blue-800">
                  <li>• Use high-quality example RFP responses</li>
                  <li>• Include company capability documents</li>
                  <li>• Ensure PDFs are text-searchable</li>
                  <li>• Review and customize the generated response</li>
                </ul>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Back button */}
            <button
              onClick={handleReset}
              className="inline-flex items-center px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            >
              ← Generate Another Response
            </button>

            {/* Response */}
            {result.rfp_response ? (
              <ResponseViewer
                response={result.rfp_response}
                analysis={result.analysis}
                pdfUrl={result.docx_download_url}
                processingTime={result.processing_time_seconds}
              />
            ) : result.docx_download_url ? (
              // Streaming mode - show simple download card
              <div className="bg-white rounded-xl shadow-sm p-8 text-center">
                <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100 mb-4">
                  <Download className="h-8 w-8 text-green-600" />
                </div>
                <h2 className="text-xl font-semibold text-gray-900 mb-2">
                  RFP Response Generated!
                </h2>
                <p className="text-gray-600 mb-6">
                  Your proposal document is ready for download.
                </p>
                <a
                  href={`/api${result.docx_download_url}`}
                  download
                  className="inline-flex items-center px-6 py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 transition-colors"
                >
                  <Download className="h-5 w-5 mr-2" />
                  Download DOCX
                </a>
              </div>
            ) : null}
          </div>
        ))}

        {activeTab === 'custom' && (
          <CustomFlow
            defaultEnablePlanner={config?.enable_planner ?? false}
            defaultEnableCritiquer={config?.enable_critiquer ?? false}
            loadRunId={customFlowLoadRequest?.runId ?? null}
            loadRunNonce={customFlowLoadRequest?.nonce ?? 0}
          />
        )}

        {activeTab === 'config' && (
          <PromptsViewer
            prompts={prompts}
            loading={promptsLoading}
            error={promptsError}
            onSavePrompt={handleSavePrompt}
            frontEndAuthEnabled={config?.front_end_auth ?? false}
            frontEndRequiredRole={requiredFrontEndRole}
            userRoles={roles}
            canModifyPrompts={canAccessPrompts}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-sm text-gray-500">
            Powered by Microsoft Agent Framework
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
