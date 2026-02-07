/**
 * Response viewer for generated RFP outputs.
 */

import { AlertCircle, CheckCircle, Download, FileText } from 'lucide-react';
import type { RFPAnalysis, RFPResponse } from '../types';
import { getDownloadUrl } from '../services/api';

interface ResponseViewerProps {
  response: RFPResponse;
  analysis?: RFPAnalysis;
  pdfUrl?: string; // Legacy prop name; currently points to DOCX URL
  processingTime?: number;
}

export function ResponseViewer({
  response,
  analysis,
  pdfUrl,
  processingTime,
}: ResponseViewerProps) {
  const isDocx = pdfUrl?.endsWith('.docx');
  const downloadLabel = isDocx ? 'Download DOCX' : 'Download Document';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Generated RFP Response</h2>
          {processingTime && (
            <p className="text-sm text-gray-500">
              Generated in {processingTime.toFixed(1)} seconds
            </p>
          )}
        </div>
        {pdfUrl && (
          <a
            href={getDownloadUrl(pdfUrl)}
            download
            className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <Download className="h-4 w-4 mr-2" />
            {downloadLabel}
          </a>
        )}
      </div>

      {analysis && (
        <div className="bg-blue-50 rounded-lg p-4 space-y-3">
          <h3 className="font-medium text-blue-900">RFP Analysis Summary</h3>
          <p className="text-sm text-blue-800">{analysis.summary}</p>
          <div className="grid grid-cols-2 gap-4 mt-4">
            <div>
              <p className="text-xs font-medium text-blue-700 uppercase">Requirements</p>
              <p className="text-lg font-semibold text-blue-900">{analysis.requirements.length}</p>
              <div className="mt-2 space-y-1">
                {analysis.requirements.slice(0, 3).map((req) => (
                  <div key={req.id} className="flex items-center text-xs">
                    {req.is_mandatory ? (
                      <AlertCircle className="h-3 w-3 text-red-500 mr-1" />
                    ) : (
                      <CheckCircle className="h-3 w-3 text-green-500 mr-1" />
                    )}
                    <span className="text-blue-700 truncate">{req.description}</span>
                  </div>
                ))}
              </div>
            </div>

            {analysis.submission_requirements && (
              <div>
                <p className="text-xs font-medium text-blue-700 uppercase">Submission</p>
                {analysis.submission_requirements.deadline && (
                  <p className="text-sm text-blue-800">
                    Deadline: {analysis.submission_requirements.deadline}
                  </p>
                )}
                {analysis.submission_requirements.page_limit && (
                  <p className="text-sm text-blue-800">
                    Page Limit: {analysis.submission_requirements.page_limit}
                  </p>
                )}
                {analysis.submission_requirements.format && (
                  <p className="text-sm text-blue-800">
                    Format: {analysis.submission_requirements.format}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
          <div className="flex items-center">
            <FileText className="h-5 w-5 text-gray-500 mr-2" />
            <span className="font-medium text-gray-700">Generated Document Code</span>
          </div>
        </div>

        <pre className="p-4 text-xs overflow-x-auto whitespace-pre-wrap text-gray-800">
          {response.document_code}
        </pre>
      </div>
    </div>
  );
}
