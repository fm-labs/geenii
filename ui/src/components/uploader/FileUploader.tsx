import { useRef, useState } from "react";
import { AlertCircle, CheckCircle, File, Upload, X } from "lucide-react";

const FileUploader = ({
                          allowedMimeTypes = [],
                          maxFileSize = 10 * 1024 * 1024, // 10MB default
                          onFilesUploaded = (_files: any) => {},
                          multiple = true
                      }) => {
    const [files, setFiles] = useState([]);
    const [dragActive, setDragActive] = useState(false);
    const fileInputRef = useRef(null);

    const generateId = () => Math.random().toString(36).substr(2, 9);

    const validateFile = (file) => {
        if (allowedMimeTypes.length > 0 && !allowedMimeTypes.includes(file.type)) {
            return `File type ${file.type} is not allowed`;
        }
        if (file.size > maxFileSize) {
            return `File size exceeds ${(maxFileSize / 1024 / 1024).toFixed(1)}MB limit`;
        }
        return null;
    };

    const simulateUpload = (fileId) => {
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 15;
            if (progress >= 100) {
                progress = 100;
                clearInterval(interval);
                setFiles(prev => prev.map(f =>
                    f.id === fileId
                        ? { ...f, progress: 100, status: 'completed' }
                        : f
                ));
            } else {
                setFiles(prev => prev.map(f =>
                    f.id === fileId
                        ? { ...f, progress: Math.round(progress) }
                        : f
                ));
            }
        }, 200);
    };

    const handleFiles = (fileList: FileList) => {
        const newFiles = Array.from(fileList).map(file => {
            const id = generateId();
            const error = validateFile(file);

            return {
                id,
                file,
                name: file.name,
                size: file.size,
                type: file.type,
                progress: error ? 0 : 0,
                status: error ? 'error' : 'uploading',
                error
            };
        });

        setFiles(prev => [...prev, ...newFiles]);

        // Start upload simulation for valid files
        newFiles.forEach(fileObj => {
            if (!fileObj.error) {
                setTimeout(() => simulateUpload(fileObj.id), 100);
            }
        });

        // Call callback with successfully uploaded files
        const validFiles = newFiles.filter(f => !f.error).map(f => f.file);
        if (validFiles.length > 0) {
            onFilesUploaded(validFiles);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);

        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files);
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
    };

    const handleFileInput = (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFiles(e.target.files);
        }
    };

    const removeFile = (fileId) => {
        setFiles(prev => prev.filter(f => f.id !== fileId));
    };

    const formatFileSize = (bytes) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const getStatusIcon = (status) => {
        switch (status) {
            case 'completed':
                return <CheckCircle className="w-5 h-5 text-green-500" />;
            case 'error':
                return <AlertCircle className="w-5 h-5 text-red-500" />;
            default:
                return <File className="w-5 h-5 text-blue-500" />;
        }
    };

    return (
        <div className="w-full max-w-2xl mx-auto p-6">
            {/* Upload Area */}
            <div
                className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                    dragActive
                        ? 'border-blue-400 bg-blue-50'
                        : 'border-gray-300 hover:border-gray-400'
                }`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    multiple={multiple}
                    accept={allowedMimeTypes.join(',')}
                    onChange={handleFileInput}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />

                <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-lg font-medium text-gray-700 mb-2">
                    Drop files here or click to upload
                </p>
                <p className="text-sm text-gray-500">
                    {allowedMimeTypes.length > 0
                        ? `Allowed types: ${allowedMimeTypes.join(', ')}`
                        : 'All file types allowed'
                    }
                </p>
                <p className="text-sm text-gray-500">
                    Max size: {(maxFileSize / 1024 / 1024).toFixed(1)}MB
                </p>
            </div>

            {/* File List */}
            {files.length > 0 && (
                <div className="mt-6">
                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                        Uploaded Files ({files.length})
                    </h3>

                    <div className="space-y-3">
                        {files.map((fileObj) => (
                            <div
                                key={fileObj.id}
                                className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm"
                            >
                                <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center space-x-3 flex-1 min-w-0">
                                        {getStatusIcon(fileObj.status)}
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-gray-900 truncate">
                                                {fileObj.name}
                                            </p>
                                            <p className="text-xs text-gray-500">
                                                {formatFileSize(fileObj.size)} • {fileObj.type}
                                            </p>
                                        </div>
                                    </div>

                                    <button
                                        onClick={() => removeFile(fileObj.id)}
                                        className="text-gray-400 hover:text-red-500 transition-colors"
                                    >
                                        <X className="w-5 h-5" />
                                    </button>
                                </div>

                                {fileObj.error ? (
                                    <div className="text-xs text-red-600 bg-red-50 p-2 rounded">
                                        {fileObj.error}
                                    </div>
                                ) : (
                                    <div className="space-y-1">
                                        <div className="flex justify-between text-xs text-gray-600">
                      <span>
                        {fileObj.status === 'completed' ? 'Completed' : 'Uploading...'}
                      </span>
                                            <span>{fileObj.progress}%</span>
                                        </div>
                                        <div className="w-full bg-gray-200 rounded-full h-2">
                                            <div
                                                className={`h-2 rounded-full transition-all duration-300 ${
                                                    fileObj.status === 'completed'
                                                        ? 'bg-green-500'
                                                        : 'bg-blue-500'
                                                }`}
                                                style={{ width: `${fileObj.progress}%` }}
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default FileUploader;
