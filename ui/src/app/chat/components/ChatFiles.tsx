import React from "react";
import FileList, { UploadedFile } from "../../../ui/file-list";
import { ChatContext } from "./ChatContext.tsx";
import ChatFilesUploaderPopup from '@/app/chat/components/ChatFilesUploaderPopup.tsx'
import { FEATURE_CHAT_FILES_ENABLED } from '@/constants.ts'

const ChatFiles = () => {

    if (!FEATURE_CHAT_FILES_ENABLED) {
        return null;
    }

    const { files, setFiles } = React.useContext(ChatContext);
    const [showFilesPopup, setShowFilesPopup] = React.useState(false);

    const handleFileDelete = (fileId: string) => {
        const filteredFiles = files.filter(f => f.id !== fileId);
        setFiles(filteredFiles);
    };

    const handleFileDownload = (file: UploadedFile) => {
        console.log('Downloading:', file.name);
        // In a real app, you would trigger the actual download here
        alert(`Downloading: ${file.name}`);
    };

    const handleFilePreview = (file: UploadedFile) => {
        console.log('Previewing:', file.name);
        // In a real app, you would open a preview modal or navigate to preview page
        alert(`Previewing: ${file.name}`);
    };

    return (
        <div>
            {/* FileList Component */}
            <div className="border rounded-lg shadow-sm p-6 m-3">
                <FileList
                    files={files}
                    onDelete={handleFileDelete}
                    onDownload={handleFileDownload}
                    onPreview={handleFilePreview}
                    showThumbnails={true}
                    gridView={true}
                />
            </div>
            {/* FileUpload */}
            <ChatFilesUploaderPopup show={showFilesPopup} onClose={() => setShowFilesPopup(false)} />
        </div>
    );
};

export default ChatFiles;
