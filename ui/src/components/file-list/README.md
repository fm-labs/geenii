# FileList Component

A comprehensive React TypeScript component for displaying uploaded files with thumbnails, file icons, and interactive features.

## Features

- **Dual View Modes**: Switch between grid and list views
- **Smart Thumbnails**: Automatic thumbnail generation for images with fallback to file icons
- **File Type Icons**: Color-coded icons for different file types (images, videos, documents, etc.)
- **File Selection**: Multi-select functionality with select all/clear options
- **Interactive Actions**: Preview, download, and delete functionality
- **Responsive Design**: Mobile-friendly layout that adapts to screen size
- **TypeScript Support**: Full type safety and IntelliSense support

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `files` | `UploadedFile[]` | Required | Array of uploaded files to display |
| `onDelete` | `(fileId: string) => void` | Optional | Callback when delete button is clicked |
| `onDownload` | `(file: UploadedFile) => void` | Optional | Callback when download button is clicked |
| `onPreview` | `(file: UploadedFile) => void` | Optional | Callback when preview button is clicked |
| `showThumbnails` | `boolean` | `true` | Whether to show thumbnails for images |
| `gridView` | `boolean` | `false` | Whether to use grid view instead of list view |

## Types

### UploadedFile

```typescript
interface UploadedFile {
  id: string;           // Unique identifier
  name: string;         // File name
  size: number;         // File size in bytes
  type: string;         // MIME type
  url?: string;         // Optional download URL
  file?: File;          // Optional File object for thumbnails
  uploadedAt: Date;     // Upload timestamp
  thumbnailUrl?: string; // Optional pre-generated thumbnail URL
}
```

## Usage

### Basic Usage

```tsx
import FileList, { UploadedFile } from './FileList';

const files: UploadedFile[] = [
  {
    id: '1',
    name: 'image.jpg',
    size: 1024000,
    type: 'image/jpeg',
    uploadedAt: new Date(),
  },
  {
    id: '2',
    name: 'document.pdf',
    size: 2048000,
    type: 'application/pdf',
    uploadedAt: new Date(),
  }
];

function App() {
  return (
    <FileList
      files={files}
      onDelete={(fileId) => console.log('Delete:', fileId)}
      onDownload={(file) => console.log('Download:', file.name)}
      onPreview={(file) => console.log('Preview:', file.name)}
    />
  );
}
```

### Grid View

```tsx
<FileList
  files={files}
  gridView={true}
  showThumbnails={true}
  onDelete={handleDelete}
/>
```

### With File Upload Integration

```tsx
import { useState } from 'react';
import FileList, { UploadedFile } from './FileList';

function FileManager() {
  const [files, setFiles] = useState<UploadedFile[]>([]);

  const handleFilesUploaded = (newFiles: File[]) => {
    const uploadedFiles: UploadedFile[] = newFiles.map(file => ({
      id: Math.random().toString(36),
      name: file.name,
      size: file.size,
      type: file.type,
      file: file,
      uploadedAt: new Date(),
    }));
    
    setFiles(prev => [...prev, ...uploadedFiles]);
  };

  const handleDelete = (fileId: string) => {
    setFiles(prev => prev.filter(f => f.id !== fileId));
  };

  return (
    <div>
      {/* Your file uploader component here */}
      <FileList
        files={files}
        onDelete={handleDelete}
        gridView={false}
      />
    </div>
  );
}
```

## File Type Support

The component automatically detects and displays appropriate icons for:

- **Images**: `.jpg`, `.png`, `.gif`, `.webp`, etc.
- **Videos**: `.mp4`, `.avi`, `.mov`, `.webm`, etc.
- **Audio**: `.mp3`, `.wav`, `.ogg`, `.flac`, etc.
- **Documents**: `.pdf`, `.doc`, `.docx`, `.txt`, etc.
- **Spreadsheets**: `.xlsx`, `.csv`, `.xls`, etc.
- **Archives**: `.zip`, `.rar`, `.tar`, `.gz`, etc.
- **Code**: `.js`, `.ts`, `.html`, `.css`, `.json`, etc.

## Styling

The component uses Tailwind CSS classes and is fully customizable. Key styling features:

- Responsive grid layout (2-6 columns based on screen size)
- Hover effects and smooth transitions
- Color-coded file type icons
- Selection states with visual feedback
- Mobile-friendly touch targets

## Dependencies

- React 18+
- TypeScript 4+
- lucide-react (for icons)
- Tailwind CSS (for styling)

## Browser Support

- Modern browsers with support for:
  - `URL.createObjectURL()` for thumbnail generation
  - CSS Grid and Flexbox
  - ES6+ features