/**
 * Main Application Component
 */

import React, { useState } from 'react';
import { Send, Loader, AlertCircle } from 'lucide-react';
import { Header, FileUpload, ProgressSteps, ResponseViewer } from './components';
import { generateRFP } from './services/api';
import type { GenerateRFPResponse } from './types';

const WORKFLOW_STEPS = [
  { id: 'upload', name: 'Upload Documents', description: 'Preparing your files' },
  { id: 'analyze', name: 'Analyze RFP', description: 'Extracting requirements' },
  { id: 'generate', name: 'Generate Sections', description: 'Creating proposal content' },
  { id: 'execute_code', name: 'Execute Code', description: 'Generating diagrams, charts & tables' },
  { id: 'review', name: 'Review Quality', description: 'Checking compliance' },
  { id: 'revise', name: 'Revise (if needed)', description: 'Improving based on feedback' },
];

function App() {
  // Form state
  const [rfpFile, setRfpFile] = useState<File[]>([]);
  const [exampleFiles, setExampleFiles] = useState<File[]>([]);
  const [contextFiles, setContextFiles] = useState<File[]>([]);

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Result state
  const [result, setResult] = useState<GenerateRFPResponse | null>(null);

  const canSubmit = rfpFile.length > 0 && exampleFiles.length > 0 && !isProcessing;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setIsProcessing(true);
    setError(null);
    setResult(null);
    setCurrentStep('upload');
    setCompletedSteps([]);

    try {
      // Simulate step progress
      setCompletedSteps(['upload']);
      setCurrentStep('analyze');

      const response = await generateRFP(
        rfpFile[0],
        exampleFiles,
        contextFiles.length > 0 ? contextFiles : undefined
      );

      // Mark all steps complete
      setCompletedSteps(['upload', 'analyze', 'generate', 'execute_code', 'review', 'revise']);
      setCurrentStep(null);
      setResult(response);
    } catch (err) {
      console.error('Generation failed:', err);
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
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
        </div>

        {!result ? (
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
                    <div>
                      <p className="font-medium text-red-800">Generation Failed</p>
                      <p className="text-sm text-red-700 mt-1">{error}</p>
                    </div>
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
                  steps={WORKFLOW_STEPS}
                  currentStep={currentStep}
                  completedSteps={completedSteps}
                />
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
            {result.rfp_response && (
              <ResponseViewer
                response={result.rfp_response}
                analysis={result.analysis}
                pdfUrl={result.pdf_download_url}
                processingTime={result.processing_time_seconds}
              />
            )}
          </div>
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
