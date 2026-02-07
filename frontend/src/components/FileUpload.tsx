/**
 * File Upload Component with drag-and-drop
 */

import { useCallback } from 'react';
import { useDropzone, Accept } from 'react-dropzone';
import { Upload, X, FileText } from 'lucide-react';

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
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      
      {description && (
        <p className="text-sm text-gray-500">{description}</p>
      )}

      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? 'active' : ''}`}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto h-12 w-12 text-gray-400" />
        <p className="mt-2 text-sm text-gray-600">
          {isDragActive
            ? 'Drop files here...'
            : `Drag & drop PDF${multiple ? 's' : ''} here, or click to select`}
        </p>
        <p className="mt-1 text-xs text-gray-500">
          {multiple ? `Up to ${maxFiles} files` : 'Single file only'}
        </p>
      </div>

      {files.length > 0 && (
        <div className="mt-4 space-y-2">
          {files.map((file, index) => (
            <div
              key={`${file.name}-${index}`}
              className="flex items-center justify-between bg-gray-50 rounded-lg p-3"
            >
              <div className="flex items-center space-x-3">
                <FileText className="h-5 w-5 text-red-500" />
                <div>
                  <p className="text-sm font-medium text-gray-700">{file.name}</p>
                  <p className="text-xs text-gray-500">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => removeFile(index)}
                className="p-1 hover:bg-gray-200 rounded-full transition-colors"
              >
                <X className="h-4 w-4 text-gray-500" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
