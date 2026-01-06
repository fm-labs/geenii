import React, { useState } from 'react';
import FileList, { UploadedFile } from './FileList';

// Demo component to showcase the FileList functionality
const FileListDemo: React.FC = () => {
  const [gridView, setGridView] = useState(false);
  const [showThumbnails, setShowThumbnails] = useState(true);

  // Sample files for demonstration
  const sampleFiles: UploadedFile[] = [
    {
      id: '1',
      name: 'summer-vacation.jpg',
      size: 2048000,
      type: 'image/jpeg',
      uploadedAt: new Date(Date.now() - 86400000), // 1 day ago
      thumbnailUrl: 'https://picsum.photos/200/200?random=1',
    },
    {
      id: '2',
      name: 'project-proposal.pdf',
      size: 1024000,
      type: 'application/pdf',
      uploadedAt: new Date(Date.now() - 3600000), // 1 hour ago
    },
    {
      id: '3',
      name: 'data-analysis.xlsx',
      size: 512000,
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      uploadedAt: new Date(Date.now() - 1800000), // 30 minutes ago
    },
    {
      id: '4',
      name: 'presentation-video.mp4',
      size: 15360000,
      type: 'video/mp4',
      uploadedAt: new Date(Date.now() - 7200000), // 2 hours ago
    },
    {
      id: '5',
      name: 'background-music.mp3',
      size: 3072000,
      type: 'audio/mpeg',
      uploadedAt: new Date(Date.now() - 10800000), // 3 hours ago
    },
    {
      id: '6',
      name: 'source-code.zip',
      size: 5120000,
      type: 'application/zip',
      uploadedAt: new Date(Date.now() - 14400000), // 4 hours ago
    },
    {
      id: '7',
      name: 'readme.txt',
      size: 2048,
      type: 'text/plain',
      uploadedAt: new Date(Date.now() - 18000000), // 5 hours ago
    },
    {
      id: '8',
      name: 'app.tsx',
      size: 8192,
      type: 'application/typescript',
      uploadedAt: new Date(Date.now() - 21600000), // 6 hours ago
    }
  ];

  const [files, setFiles] = useState<UploadedFile[]>(sampleFiles);

  const handleDelete = (fileId: string) => {
    setFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const handleDownload = (file: UploadedFile) => {
    console.log('Downloading:', file.name);
    // In a real app, you would trigger the actual download here
    alert(`Downloading: ${file.name}`);
  };

  const handlePreview = (file: UploadedFile) => {
    console.log('Previewing:', file.name);
    // In a real app, you would open a preview modal or navigate to preview page
    alert(`Previewing: ${file.name}`);
  };

  return (
    <div className="_min-h-screen _bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Files
          </h1>
        </div>

        {/* Controls */}
        <div className="bg-white rounded-lg p-6 mb-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Controls</h2>
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={gridView}
                onChange={(e) => setGridView(e.target.checked)}
                className="rounded border-gray-300"
              />
              <span className="text-sm text-gray-700">Grid View</span>
            </label>
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={showThumbnails}
                onChange={(e) => setShowThumbnails(e.target.checked)}
                className="rounded border-gray-300"
              />
              <span className="text-sm text-gray-700">Show Thumbnails</span>
            </label>
          </div>
        </div>

        {/* FileList Component */}
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <FileList
            files={files}
            onDelete={handleDelete}
            onDownload={handleDownload}
            onPreview={handlePreview}
            showThumbnails={showThumbnails}
            gridView={gridView}
          />
        </div>
      </div>
    </div>
  );
};

export default FileListDemo;
