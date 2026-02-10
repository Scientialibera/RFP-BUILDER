/**
 * Main Application Component
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Loader, AlertCircle, RefreshCw, Download, FileText, ChevronDown, CheckSquare, Lightbulb, UploadCloud } from 'lucide-react';
import { Header, FileUpload, ProgressSteps, ResponseViewer, CustomFlow, PromptsViewer } from './components';
import { RunsHistory } from './components/RunsHistory';
import { generateRFPStream, getConfig, getPrompts, updatePrompt } from './services/api';
import type { GenerateRFPResponse, ConfigResponse, WorkflowStepConfig, PromptsResponse } from './types';
import { useAuth } from './context/AuthContext';
import type { NavTab } from './components/Header';

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
  const [streamLogs, setStreamLogs] = useState<string[]>([]);

  // Result state
  const [result, setResult] = useState<GenerateRFPResponse | null>(null);

  // Navigation state
  const [activeTab, setActiveTab] = useState<NavTab>('standard');
  const [customFlowLoadRequest, setCustomFlowLoadRequest] = useState<{ runId: string; nonce: number } | null>(null);
  const [prompts, setPrompts] = useState<PromptsResponse | null>(null);
  const [promptsLoading, setPromptsLoading] = useState(false);
  const [promptsError, setPromptsError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [rightTab, setRightTab] = useState<'logs' | 'artifacts'>('logs');

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
    setStreamLogs([]);
    setRightTab('logs');

    try {
      setCompletedSteps(['upload']);

      let downloadUrl: string | undefined;

      await generateRFPStream(
        rfpFile[0],
        exampleFiles,
        contextFiles.length > 0 ? contextFiles : undefined,
        (event) => {
          if (event.step) {
            const stepId = event.step.toLowerCase().replace(/ /g, '_');
            const stepIndex = workflowSteps.findIndex(s => s.id === stepId);
            if (stepIndex >= 0) {
              const completed = workflowSteps.slice(0, stepIndex).map(s => s.id);
              setCompletedSteps(completed);
              setCurrentStep(stepId);
            }
          }

          // Capture log messages
          if (event.message) {
            const timestamp = new Date().toLocaleTimeString();
            setStreamLogs(prev => [...prev, `[${timestamp}] ${event.message}`]);
          }

          if (event.event === 'complete' && event.data?.download_url) {
            downloadUrl = event.data.download_url as string;
          }
          if (event.event === 'complete' && !event.data?.download_url && (event as { download_url?: string }).download_url) {
            downloadUrl = (event as { download_url?: string }).download_url;
          }

          if (event.event === 'error') {
            throw new Error(event.message || 'An error occurred during generation');
          }
        },
        {
          enablePlanner: effectivePlanner,
          enableCritiquer: effectiveCritiquer,
        }
      );

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
    setStreamLogs([]);
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Left Sidebar */}
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {/* Main Content Area - offset by sidebar width */}
      <div className="ml-60 min-h-screen flex flex-col">

        {null}

        {/* Page Body */}
        <main className="flex-1 p-6">

          {/* ========= STANDARD RUN ========= */}
          {activeTab === 'standard' && (
            <div className="flex gap-6">

              {/* Center content */}
              <div className="flex-1 min-w-0">
                {!result ? (
                  <form onSubmit={handleSubmit}>
                    {/* Title */}
                    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                      <h1 className="text-2xl font-bold text-gray-900 text-center">
                        RFP Response Generator
                      </h1>
                      <p className="mt-1 text-sm text-gray-500 text-center">
                        Upload your RFP and examples to generate a professional proposal response
                      </p>
                    </div>

                    {/* Upload Cards Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                      <FileUpload
                        label="Target RFP Document"
                        description="The RFP you want to respond to"
                        files={rfpFile}
                        onFilesChange={setRfpFile}
                        multiple={false}
                        required
                      />

                      <FileUpload
                        label="Example RFP Responses"
                        description="1-5 previous RFP responses to use as style references"
                        files={exampleFiles}
                        onFilesChange={setExampleFiles}
                        multiple
                        maxFiles={5}
                        required
                      />

                      <FileUpload
                        label="Company Context (Optional)"
                        description="Documents about your company's capabilities, etc."
                        files={contextFiles}
                        onFilesChange={setContextFiles}
                        multiple
                        maxFiles={5}
                      />
                    </div>

                    {/* Tips Bar */}
                    <div className="bg-white rounded-xl border border-gray-200 px-5 py-3 mb-4 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Lightbulb className="h-4 w-4 text-primary-500" />
                        <span className="text-sm font-medium text-gray-700">Tips for Best Results</span>
                      </div>
                      <div className="flex items-center gap-4">
                        <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">
                          <CheckSquare className="h-3.5 w-3.5 text-primary-500" />
                          Upload tables as images
                        </label>
                        <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">
                          <CheckSquare className="h-3.5 w-3.5 text-primary-500" />
                          Improves accuracy for table-heavy documents
                        </label>
                      </div>
                    </div>

                    {/* Advanced Options */}
                    <div className="bg-white rounded-xl border border-gray-200 mb-6">
                      <button
                        type="button"
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className="w-full flex items-center justify-between px-5 py-3 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                      >
                        <span className="font-medium">Advanced Options</span>
                        <ChevronDown className={`h-4 w-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
                      </button>

                      {showAdvanced && config && (
                        <div className="px-5 pb-4 border-t border-gray-100 pt-4 space-y-3">
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
                                effectivePlanner ? 'bg-primary-500' : 'bg-gray-200'
                              }`}
                            >
                              <span
                                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                  effectivePlanner ? 'translate-x-5' : 'translate-x-0'
                                }`}
                              />
                            </button>
                          </label>

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
                                effectiveCritiquer ? 'bg-primary-500' : 'bg-gray-200'
                              }`}
                            >
                              <span
                                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                  effectiveCritiquer ? 'translate-x-5' : 'translate-x-0'
                                }`}
                              />
                            </button>
                          </label>

                          {(enablePlanner !== null || enableCritiquer !== null) && (
                            <button
                              type="button"
                              onClick={() => { setEnablePlanner(null); setEnableCritiquer(null); }}
                              className="text-xs text-gray-400 hover:text-gray-600"
                            >
                              Reset to server defaults
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Generate Button */}
                    <div className="mb-6">
                      <button
                        type="submit"
                        disabled={!canSubmit}
                        className="w-full inline-flex items-center justify-center px-6 py-3 bg-primary-500 text-white font-semibold rounded-xl hover:bg-primary-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors shadow-md shadow-primary-200"
                      >
                        {isProcessing ? (
                          <>
                            <Loader className="h-5 w-5 mr-2 animate-spin" />
                            Generating...
                          </>
                        ) : (
                          <>
                            <UploadCloud className="h-5 w-5 mr-2" />
                            Generate Response
                          </>
                        )}
                      </button>
                    </div>

                    {/* Error */}
                    {error && (
                      <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start mb-6">
                        <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 mr-3 flex-shrink-0" />
                        <div className="flex-1">
                          <p className="font-medium text-red-800">Generation Failed</p>
                          <p className="text-sm text-red-700 mt-1">{error}</p>
                          {connectionLost && (
                            <button
                              type="button"
                              onClick={handleReload}
                              className="mt-3 inline-flex items-center px-3 py-1.5 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors"
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
                      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 flex items-center justify-between mb-6">
                        <div className="flex items-center">
                          <AlertCircle className="h-5 w-5 text-yellow-500 mr-3" />
                          <p className="text-sm text-yellow-800">Connection to server lost</p>
                        </div>
                        <button
                          type="button"
                          onClick={handleReload}
                          className="inline-flex items-center px-3 py-1.5 bg-yellow-600 text-white text-sm font-medium rounded-lg hover:bg-yellow-700 transition-colors"
                        >
                          <RefreshCw className="h-4 w-4 mr-1.5" />
                          Reload
                        </button>
                      </div>
                    )}
                  </form>
                ) : (
                  <div className="space-y-6">
                    <button
                      onClick={handleReset}
                      className="inline-flex items-center px-4 py-2 text-gray-600 hover:text-gray-900 bg-white hover:bg-gray-50 rounded-lg border border-gray-200 transition-colors shadow-sm"
                    >
                      &larr; Generate Another Response
                    </button>

                    {result.rfp_response ? (
                      <ResponseViewer
                        response={result.rfp_response}
                        analysis={result.analysis}
                        pdfUrl={result.docx_download_url}
                        processingTime={result.processing_time_seconds}
                      />
                    ) : result.docx_download_url ? (
                      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
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
                          className="inline-flex items-center px-6 py-3 bg-primary-500 text-white font-medium rounded-xl hover:bg-primary-600 transition-colors shadow-md shadow-primary-200"
                        >
                          <Download className="h-5 w-5 mr-2" />
                          Download DOCX
                        </a>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>

              {/* Right Panel: Logs & Artifacts only */}
              <div className="w-72 flex-shrink-0">
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                  {/* Tab bar */}
                  <div className="flex items-center gap-1 px-4 pt-4 pb-3">
                    {(['logs', 'artifacts'] as const).map((tab) => (
                      <button
                        key={tab}
                        type="button"
                        onClick={() => setRightTab(tab)}
                        className={`status-tab ${rightTab === tab ? 'active' : ''}`}
                      >
                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                      </button>
                    ))}
                  </div>

                  <div className="px-4 pb-4">
                    {rightTab === 'logs' && (
                      <div className="space-y-2">
                        {/* Progress Steps */}
                        {(isProcessing || completedSteps.length > 0) && (
                          <div className="mb-3">
                            <ProgressSteps
                              steps={workflowSteps}
                              currentStep={currentStep}
                              completedSteps={completedSteps}
                            />
                          </div>
                        )}

                        {/* Stream logs */}
                        {streamLogs.length > 0 ? (
                          <div className="max-h-64 overflow-y-auto border border-gray-100 rounded-lg p-2 bg-gray-50">
                            {streamLogs.map((log, idx) => (
                              <p key={idx} className="text-[11px] text-gray-600 font-mono leading-relaxed">
                                {log}
                              </p>
                            ))}
                          </div>
                        ) : (
                          <div className="text-xs text-gray-400 py-6 text-center">
                            Logs will appear here during generation
                          </div>
                        )}
                      </div>
                    )}

                    {rightTab === 'artifacts' && (
                      <div>
                        {result?.docx_download_url ? (
                          <div className="space-y-2">
                            <a
                              href={`/api${result.docx_download_url}`}
                              download
                              className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                            >
                              <div className="flex items-center gap-2">
                                <FileText className="h-4 w-4 text-primary-500" />
                                <span className="text-xs font-medium text-gray-700">Final Proposal.docx</span>
                              </div>
                              <Download className="h-3.5 w-3.5 text-gray-400" />
                            </a>
                          </div>
                        ) : (
                          <div className="text-xs text-gray-400 py-6 text-center">
                            Generated artifacts will appear here
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========= CUSTOM RUN ========= */}
          {activeTab === 'custom' && (
            <CustomFlow
              defaultEnablePlanner={config?.enable_planner ?? false}
              defaultEnableCritiquer={config?.enable_critiquer ?? false}
              loadRunId={customFlowLoadRequest?.runId ?? null}
              loadRunNonce={customFlowLoadRequest?.nonce ?? 0}
            />
          )}

          {/* ========= CONFIG ========= */}
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

          {/* ========= LAST RUNS ========= */}
          {activeTab === 'runs' && (
            <RunsHistory
              inline
              onLoadToCustomFlow={(runId) => {
                setCustomFlowLoadRequest({ runId, nonce: Date.now() });
                setActiveTab('custom');
              }}
            />
          )}
        </main>

        {/* Footer */}
        <footer className="border-t border-gray-200 bg-white">
          <div className="px-6 py-4">
            <p className="text-center text-xs text-gray-400">
              Powered by Microsoft Agent Framework
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default App;
