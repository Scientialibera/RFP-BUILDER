/**
 * File Upload Component with drag-and-drop - Card style
 */

import { useCallback } from 'react';
import { useDropzone, Accept } from 'react-dropzone';
import { UploadCloud, X, FileText, ChevronDown } from 'lucide-react';

interface FileUploadProps {
  label: string;
  description?: string;
  files: File[];
  onFilesChange: (files: File[]) => void;
  multiple?: boolean;
  accept?: Accept;
  maxFiles?: number;
  required?: boolean;
}

export function FileUpload({
  label,
  description,
  files,
  onFilesChange,
  multiple = false,
  accept = { 'application/pdf': ['.pdf'] },
  maxFiles = 10,
  required = false,
}: FileUploadProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (multiple) {
        const newFiles = [...files, ...acceptedFiles].slice(0, maxFiles);
        onFilesChange(newFiles);
      } else {
        onFilesChange(acceptedFiles.slice(0, 1));
      }
    },
    [files, multiple, maxFiles, onFilesChange]
  );

  const removeFile = (index: number) => {
    const newFiles = files.filter((_, i) => i !== index);
    onFilesChange(newFiles);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    multiple,
    maxFiles: multiple ? maxFiles : 1,
  });

  return (
    <div className="upload-card">
      {/* Card Header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">
            {label}
            {required && <span className="text-red-400 ml-0.5">*</span>}
          </h3>
          {description && (
            <p className="text-xs text-gray-400 mt-0.5">{description}</p>
          )}
        </div>
        <ChevronDown className="h-4 w-4 text-gray-400" />
      </div>

      {/* Upload Zone */}
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? 'active' : ''}`}
      >
        <input {...getInputProps()} />
        <UploadCloud className="mx-auto h-10 w-10 text-primary-400" />
        <p className="mt-2 text-xs text-gray-500">
          {isDragActive
            ? 'Drop files here...'
            : `Drag & drop or click to select`}
        </p>
      </div>

      {/* Upload Button */}
      <button
        type="button"
        {...getRootProps()}
        className="w-full mt-3 inline-flex items-center justify-center px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 transition-colors shadow-sm"
      >
        <UploadCloud className="h-4 w-4 mr-2" />
        Upload Document
      </button>

      {/* File Type Badges */}
      <div className="flex items-center gap-2 mt-3">
        <span className="file-badge file-badge-docx">
          <FileText className="h-3 w-3 mr-1" />
          DOCX
        </span>
        <span className="file-badge file-badge-pdf">
          <FileText className="h-3 w-3 mr-1" />
          PDF
        </span>
        {multiple && (
          <span className="text-xs text-gray-400 ml-auto">
            Up to {maxFiles} files
          </span>
        )}
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="mt-3 space-y-2">
          {files.map((file, index) => (
            <div
              key={`${file.name}-${index}`}
              className="flex items-center justify-between bg-gray-50 rounded-lg p-2.5 border border-gray-100"
            >
              <div className="flex items-center space-x-2.5 min-w-0">
                <FileText className="h-4 w-4 text-primary-500 flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-xs font-medium text-gray-700 truncate">{file.name}</p>
                  <p className="text-[10px] text-gray-400">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); removeFile(index); }}
                className="p-1 hover:bg-gray-200 rounded-full transition-colors flex-shrink-0"
              >
                <X className="h-3.5 w-3.5 text-gray-400" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
