import React, { useState, useEffect } from 'react';
import {
  File,
  FileText,
  FileImage,
  FileVideo,
  FileAudio,
  FileCode,
  FileSpreadsheet,
  FileArchive,
  Download,
  Trash2,
  Eye,
  MoreHorizontal
} from 'lucide-react';

// Types
export interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  url?: string;
  file?: File;
  uploadedAt: Date;
  thumbnailUrl?: string;
}

interface FileListProps {
  files: UploadedFile[];
  onDelete?: (fileId: string) => void;
  onDownload?: (file: UploadedFile) => void;
  onPreview?: (file: UploadedFile) => void;
  showThumbnails?: boolean;
  gridView?: boolean;
}

// File type categories
const getFileCategory = (mimeType: string): string => {
  if (mimeType.startsWith('image/')) return 'image';
  if (mimeType.startsWith('video/')) return 'video';
  if (mimeType.startsWith('audio/')) return 'audio';
  if (mimeType.includes('pdf')) return 'pdf';
  if (mimeType.includes('spreadsheet') || mimeType.includes('excel') || mimeType.includes('csv')) return 'spreadsheet';
  if (mimeType.includes('zip') || mimeType.includes('rar') || mimeType.includes('tar')) return 'archive';
  if (mimeType.includes('text') || mimeType.includes('json') || mimeType.includes('xml')) return 'text';
  if (mimeType.includes('javascript') || mimeType.includes('typescript') || mimeType.includes('html') || mimeType.includes('css')) return 'code';
  return 'file';
};

// File icon component
const FileIcon: React.FC<{ mimeType: string; className?: string }> = ({ mimeType, className = "w-8 h-8" }) => {
  const category = getFileCategory(mimeType);

  const iconProps = { className };

  switch (category) {
    case 'image':
      return <FileImage {...iconProps} className={`${className} text-green-500`} />;
    case 'video':
      return <FileVideo {...iconProps} className={`${className} text-purple-500`} />;
    case 'audio':
      return <FileAudio {...iconProps} className={`${className} text-pink-500`} />;
    case 'pdf':
      return <FileText {...iconProps} className={`${className} text-red-500`} />;
    case 'spreadsheet':
      return <FileSpreadsheet {...iconProps} className={`${className} text-green-600`} />;
    case 'archive':
      return <FileArchive {...iconProps} className={`${className} text-orange-500`} />;
    case 'text':
      return <FileText {...iconProps} className={`${className} text-blue-500`} />;
    case 'code':
      return <FileCode {...iconProps} className={`${className} text-indigo-500`} />;
    default:
      return <File {...iconProps} className={`${className} text-gray-500`} />;
  }
};

// Thumbnail component
const FileThumbnail: React.FC<{ file: UploadedFile; className?: string }> = ({
  file,
  className = "w-16 h-16"
}) => {
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(file.thumbnailUrl || null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (file.file && file.type.startsWith('image/') && !thumbnailUrl && !error) {
      const url = URL.createObjectURL(file.file);
      setThumbnailUrl(url);

      return () => URL.revokeObjectURL(url);
    }
  }, [file.file, file.type, thumbnailUrl, error]);

  if (error || !thumbnailUrl || !file.type.startsWith('image/')) {
    return (
      <div className={`${className} bg-gray-100 rounded-lg flex items-center justify-center`}>
        <FileIcon mimeType={file.type} className="w-8 h-8" />
      </div>
    );
  }

  return (
    <div className={`${className} bg-gray-100 rounded-lg overflow-hidden`}>
      <img
        src={thumbnailUrl}
        alt={file.name}
        className="w-full h-full object-cover"
        onError={() => setError(true)}
      />
    </div>
  );
};

// Utility functions
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const formatDate = (date: Date): string => {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
};

// Main FileList component
const FileList: React.FC<FileListProps> = ({
  files,
  onDelete,
  onDownload,
  onPreview,
  showThumbnails = true,
  gridView = false
}) => {
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());

  const toggleFileSelection = (fileId: string) => {
    const newSelected = new Set(selectedFiles);
    if (newSelected.has(fileId)) {
      newSelected.delete(fileId);
    } else {
      newSelected.add(fileId);
    }
    setSelectedFiles(newSelected);
  };

  const selectAll = () => {
    setSelectedFiles(new Set(files.map(f => f.id)));
  };

  const clearSelection = () => {
    setSelectedFiles(new Set());
  };

  if (files.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <File className="w-16 h-16 mx-auto mb-4 text-gray-300" />
        <p className="text-lg font-medium">No files uploaded</p>
        <p className="text-sm">Upload some files to see them here</p>
      </div>
    );
  }

  if (gridView) {
    return (
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">
            Files ({files.length})
          </h3>
          <div className="flex items-center space-x-2 text-sm">
            <button
              onClick={selectAll}
              className="text-blue-600 hover:text-blue-800"
            >
              Select All
            </button>
            {selectedFiles.size > 0 && (
              <>
                <span className="text-gray-400">|</span>
                <button
                  onClick={clearSelection}
                  className="text-gray-600 hover:text-gray-800"
                >
                  Clear ({selectedFiles.size})
                </button>
              </>
            )}
          </div>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {files.map((file) => (
            <div
              key={file.id}
              className={`group relative bg-white border rounded-lg p-3 hover:shadow-md transition-shadow ${
                selectedFiles.has(file.id) ? 'ring-2 ring-blue-500 border-blue-500' : 'border-gray-200'
              }`}
            >
              {/* Selection checkbox */}
              <div className="absolute top-2 left-2 z-10 w-auto">
                <input
                  type="checkbox"
                  checked={selectedFiles.has(file.id)}
                  onChange={() => toggleFileSelection(file.id)}
                />
              </div>

              {/* Thumbnail/Icon */}
              <div className="mb-2">
                {showThumbnails ? (
                  <FileThumbnail file={file} className="w-full h-20" />
                ) : (
                  <div className="w-full h-20 bg-gray-50 rounded flex items-center justify-center">
                    <FileIcon mimeType={file.type} className="w-10 h-10" />
                  </div>
                )}
              </div>

              {/* File info */}
              <div className="space-y-1">
                <p className="text-sm font-medium text-gray-900 truncate" title={file.name}>
                  {file.name}
                </p>
                <p className="text-xs text-gray-500">
                  {formatFileSize(file.size)}
                </p>
              </div>

              {/* Actions */}
              <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <div className="flex space-x-1">
                  {onPreview && (
                    <button
                      onClick={() => onPreview(file)}
                      className="p-1 bg-white rounded shadow-sm hover:bg-gray-50"
                      title="Preview"
                    >
                      <Eye className="w-3 h-3" />
                    </button>
                  )}
                  {onDownload && (
                    <button
                      onClick={() => onDownload(file)}
                      className="p-1 bg-white rounded shadow-sm hover:bg-gray-50"
                      title="Download"
                    >
                      <Download className="w-3 h-3" />
                    </button>
                  )}
                  {onDelete && (
                    <button
                      onClick={() => onDelete(file.id)}
                      className="p-1 bg-white rounded shadow-sm hover:bg-red-50 text-red-600"
                      title="Delete"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // List view
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">
          Files ({files.length})
        </h3>
        <div className="flex items-center space-x-2 text-sm">
          <button
            onClick={selectAll}
            className="text-blue-600 hover:text-blue-800"
          >
            Select All
          </button>
          {selectedFiles.size > 0 && (
            <>
              <span className="text-gray-400">|</span>
              <button
                onClick={clearSelection}
                className="text-gray-600 hover:text-gray-800"
              >
                Clear ({selectedFiles.size})
              </button>
            </>
          )}
        </div>
      </div>

      {/* List */}
      <div className="space-y-2">
        {files.map((file) => (
          <div
            key={file.id}
            className={`group bg-white border rounded-lg p-4 hover:shadow-sm transition-shadow ${
              selectedFiles.has(file.id) ? 'ring-2 ring-blue-500 border-blue-500' : 'border-gray-200'
            }`}
          >
            <div className="flex items-center space-x-4">
              {/* Selection checkbox */}
              <input
                type="checkbox"
                checked={selectedFiles.has(file.id)}
                onChange={() => toggleFileSelection(file.id)}
              />

              {/* Thumbnail/Icon */}
              {showThumbnails ? (
                <FileThumbnail file={file} className="w-12 h-12 flex-shrink-0" />
              ) : (
                <div className="w-12 h-12 bg-gray-50 rounded flex items-center justify-center flex-shrink-0">
                  <FileIcon mimeType={file.type} className="w-6 h-6" />
                </div>
              )}

              {/* File info */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {file.name}
                </p>
                <div className="flex items-center space-x-4 text-xs text-gray-500 mt-1">
                  <span>{formatFileSize(file.size)}</span>
                  <span>{file.type}</span>
                  <span>{formatDate(file.uploadedAt)}</span>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                {onPreview && (
                  <button
                    onClick={() => onPreview(file)}
                    className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                    title="Preview"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                )}
                {onDownload && (
                  <button
                    onClick={() => onDownload(file)}
                    className="p-2 text-gray-400 hover:text-green-600 transition-colors"
                    title="Download"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                )}
                {onDelete && (
                  <button
                    onClick={() => onDelete(file.id)}
                    className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
                <button className="p-2 text-gray-400 hover:text-gray-600 transition-colors">
                  <MoreHorizontal className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default FileList;
