/**
 * Runs History Component
 * 
 * Displays a list of past runs with details and actions.
 */

import { useState, useEffect, useCallback } from 'react';
import { 
  History, 
  FileText, 
  Download, 
  Code, 
  RefreshCw, 
  ChevronRight,
  Calendar,
  CheckCircle,
  X,
  Play,
  Loader
} from 'lucide-react';
import type { RunSummary, RunDetails, RunCodeResponse } from '../types';
import { 
  listRuns, 
  getRunDetails, 
  getRunCode, 
  regenerateDocument,
  getDownloadUrl,
  getSourceDocumentUrl,
  getRevisionDownloadUrl
} from '../services/api';

interface RunsHistoryProps {
  onClose: () => void;
  onLoadToCustomFlow?: (runId: string) => void;
}

export function RunsHistory({ onClose, onLoadToCustomFlow }: RunsHistoryProps) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<RunDetails | null>(null);
  const [codeData, setCodeData] = useState<RunCodeResponse | null>(null);
  const [editedCode, setEditedCode] = useState<string>('');
  const [showCodeEditor, setShowCodeEditor] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [regenerateMessage, setRegenerateMessage] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await listRuns();
      setRuns(response.runs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load runs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  const handleSelectRun = async (runId: string) => {
    try {
      setError(null);
      const details = await getRunDetails(runId);
      setSelectedRun(details);
      setCodeData(null);
      setShowCodeEditor(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load run details');
    }
  };

  const handleLoadCode = async () => {
    if (!selectedRun) return;
    try {
      setError(null);
      const code = await getRunCode(selectedRun.run_id);
      setCodeData(code);
      setEditedCode(code.code);
      setShowCodeEditor(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load code');
    }
  };

  const handleRegenerate = async () => {
    if (!selectedRun || !editedCode) return;
    try {
      setRegenerating(true);
      setRegenerateMessage(null);
      setError(null);
      const result = await regenerateDocument(selectedRun.run_id, editedCode);
      setRegenerateMessage(`Success! Created ${result.revision_id}`);
      // Reload run details to show new revision
      const details = await getRunDetails(selectedRun.run_id);
      setSelectedRun(details);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Regeneration failed');
    } finally {
      setRegenerating(false);
    }
  };

  const formatDate = (isoDate: string) => {
    try {
      const date = new Date(isoDate);
      return date.toLocaleString();
    } catch {
      return isoDate;
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-6xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center">
            <History className="h-6 w-6 text-primary-600 mr-3" />
            <h2 className="text-xl font-semibold text-gray-900">Past Runs</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Runs List */}
          <div className="w-80 border-r border-gray-200 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center h-32">
                <Loader className="h-6 w-6 text-primary-500 animate-spin" />
              </div>
            ) : runs.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                <History className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                <p>No runs yet</p>
              </div>
            ) : (
              <ul className="divide-y divide-gray-100">
                {runs.map((run) => (
                  <li key={run.run_id}>
                    <button
                      onClick={() => handleSelectRun(run.run_id)}
                      className={`w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors ${
                        selectedRun?.run_id === run.run_id ? 'bg-primary-50' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {run.run_id}
                          </p>
                          <div className="flex items-center mt-1 text-xs text-gray-500">
                            <Calendar className="h-3 w-3 mr-1" />
                            {formatDate(run.created_at)}
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            {run.has_docx && (
                              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-green-100 text-green-700">
                                <CheckCircle className="h-3 w-3 mr-0.5" />
                                DOCX
                              </span>
                            )}
                            {run.has_plan && (
                              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-purple-100 text-purple-700">
                                Plan
                              </span>
                            )}
                            {run.revision_count > 0 && (
                              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-blue-100 text-blue-700">
                                {run.revision_count} rev
                              </span>
                            )}
                          </div>
                        </div>
                        <ChevronRight className="h-4 w-4 text-gray-400 flex-shrink-0" />
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Run Details */}
          <div className="flex-1 overflow-y-auto p-6">
            {error && (
              <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                {error}
              </div>
            )}

            {regenerateMessage && (
              <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-4 text-green-700">
                {regenerateMessage}
              </div>
            )}

            {!selectedRun ? (
              <div className="flex items-center justify-center h-full text-gray-500">
                <div className="text-center">
                  <FileText className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                  <p>Select a run to view details</p>
                </div>
              </div>
            ) : showCodeEditor && codeData ? (
              /* Code Editor View */
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-gray-900">
                    Code Editor - {codeData.stage}
                  </h3>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowCodeEditor(false)}
                      className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
                    >
                      Back
                    </button>
                    <button
                      onClick={handleRegenerate}
                      disabled={regenerating}
                      className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                    >
                      {regenerating ? (
                        <>
                          <Loader className="h-4 w-4 mr-2 animate-spin" />
                          Regenerating...
                        </>
                      ) : (
                        <>
                          <Play className="h-4 w-4 mr-2" />
                          Regenerate Document
                        </>
                      )}
                    </button>
                  </div>
                </div>
                <textarea
                  value={editedCode}
                  onChange={(e) => setEditedCode(e.target.value)}
                  className="w-full h-[500px] font-mono text-sm p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  spellCheck={false}
                />
              </div>
            ) : (
              /* Run Details View */
              <div className="space-y-6">
                {/* Run Info */}
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">
                    {selectedRun.run_id}
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-500">Created</p>
                      <p className="text-sm font-medium text-gray-900">
                        {formatDate(selectedRun.created_at)}
                      </p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-500">Status</p>
                      <p className="text-sm font-medium text-gray-900">
                        {selectedRun.has_docx ? 'Complete' : 'No Document'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex flex-wrap gap-3">
                  {onLoadToCustomFlow && (
                    <button
                      onClick={() => onLoadToCustomFlow(selectedRun.run_id)}
                      className="inline-flex items-center px-4 py-2 border border-primary-300 text-primary-700 rounded-lg hover:bg-primary-50 transition-colors"
                    >
                      <Play className="h-4 w-4 mr-2" />
                      Continue in Custom Flow
                    </button>
                  )}
                  {selectedRun.docx_download_url && (
                    <a
                      href={getDownloadUrl(selectedRun.docx_download_url)}
                      download
                      className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
                    >
                      <Download className="h-4 w-4 mr-2" />
                      Download DOCX
                    </a>
                  )}
                  {selectedRun.code_available && (
                    <button
                      onClick={handleLoadCode}
                      className="inline-flex items-center px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <Code className="h-4 w-4 mr-2" />
                      View/Edit Code
                    </button>
                  )}
                </div>

                {/* Source Documents */}
                {selectedRun.documents.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 mb-3">
                      Source Documents
                    </h4>
                    <ul className="space-y-2">
                      {selectedRun.documents.map((doc) => (
                        <li key={doc.filename}>
                          <a
                            href={getSourceDocumentUrl(selectedRun.run_id, doc.filename)}
                            download
                            className="flex items-center px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg border border-gray-200 transition-colors"
                          >
                            <FileText className="h-4 w-4 mr-2 text-gray-400" />
                            <span className="flex-1">{doc.filename}</span>
                            <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                              {doc.file_type}
                            </span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Revisions */}
                {selectedRun.revisions.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 mb-3">
                      Revisions
                    </h4>
                    <ul className="space-y-2">
                      {selectedRun.revisions.map((rev) => (
                        <li key={rev.revision_id}>
                          <a
                            href={getRevisionDownloadUrl(
                              selectedRun.run_id,
                              rev.revision_id,
                              rev.docx_filename
                            )}
                            download
                            className="flex items-center px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg border border-gray-200 transition-colors"
                          >
                            <RefreshCw className="h-4 w-4 mr-2 text-blue-500" />
                            <span className="flex-1">{rev.revision_id}</span>
                            <span className="text-xs text-gray-500">
                              {formatDate(rev.created_at)}
                            </span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-between items-center">
          <button
            onClick={loadRuns}
            className="inline-flex items-center px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          >
            <RefreshCw className="h-4 w-4 mr-1.5" />
            Refresh
          </button>
          <p className="text-sm text-gray-500">
            {runs.length} run{runs.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>
    </div>
  );
}
