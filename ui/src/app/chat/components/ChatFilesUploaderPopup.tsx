import Popup, { PopupProps } from "../../../ui/Popup.tsx";
import FileUploader from "../../../ui/uploader/FileUploader.tsx";
import { UploadedFile } from "../../../ui/file-list";
import { useContext } from "react";
import { ChatContext } from "./ChatContext.tsx";
import { FEATURE_CHAT_FILES_ENABLED } from "../../../constants.ts";

const ChatFilesUploaderPopup = (props: Omit<PopupProps,'children'>) => {

    if (!FEATURE_CHAT_FILES_ENABLED) {
        return null;
    }

    const { files, setFiles } = useContext(ChatContext)

    const handleFilesUploaded = async (filesToUpload: File[]) => {
        console.log("Files uploaded:", filesToUpload);

        const newFiles: UploadedFile[] = [];
        for (const file of filesToUpload) {
            console.log(`File: ${file.name}, Size: ${file.size} bytes`);

            // Read file as data URL for preview
            const getFileDataUrl = async (file: File): Promise<string> => {
                // Check if FileReader is supported
                if (!window.FileReader) {
                    throw new Error("FileReader is not supported in this browser.");
                }

                // Check file size and type
                if (file.size > 5 * 1024 * 1024) { // 5MB limit
                    throw new Error("File size exceeds the maximum limit of 5MB.");
                }

                if (!file.type.startsWith("image/") && !file.type.startsWith("application/pdf") && !file.type.startsWith("text/")) {
                    throw new Error("Unsupported file type. Only images, PDFs, and text files are allowed.");
                }

                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        resolve(e.target?.result as string);
                    };
                    reader.onerror = (error) => {
                        reject(error);
                    };
                    reader.readAsDataURL(file);
                });
            };

            const thumbnailUrl = await getFileDataUrl(file).catch(error => {
                console.warn(`Error retrieving data url for ${file.name}:`, error);
                return undefined; // Return empty string if there's an error
            });

            const uploadedFile: UploadedFile = {
                id: crypto.randomUUID(),
                file: file,
                name: file.name,
                size: file.size,
                type: file.type,
                thumbnailUrl: thumbnailUrl,
                uploadedAt: new Date(),
                //progress: 100, // Assuming upload is complete
                //status: 'uploaded',
                //error: false
            };

            //setFiles((prevFiles: UploadedFile[]) => [...prevFiles, uploadedFile]);
            //const newFiles: UploadedFile[] = [...files, uploadedFile];
            newFiles.push(uploadedFile);
        }
        console.log("NEW FILES", newFiles);
        setFiles([...files, ...newFiles]);
    }

    return (
        <div>
            <Popup
                title="Upload Files"
                size="xl"
                showCloseButton={true}
                closeOnOverlayClick={true}
                {...props}
            >
                <div className="max-w-4xl mx-auto">
                    <h1 className="text-3xl font-bold text-gray-900 text-center mb-8">
                        File Upload Demo
                    </h1>

                    <FileUploader
                        allowedMimeTypes={["image/jpeg", "image/png", "image/gif", "application/pdf", "text/plain"]}
                        maxFileSize={5 * 1024 * 1024} // 5MB
                        onFilesUploaded={handleFilesUploaded}
                        multiple={true}
                    />
                </div>
            </Popup>
        </div>
    );
};

export default ChatFilesUploaderPopup;
