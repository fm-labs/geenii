import FileUploader from "./FileUploader.tsx";

const FileUploaderExample = () => {
    const handleFilesUploaded = (files) => {
        console.log("Files uploaded:", files);
    };

    return (
        <div className="min-h-screen bg-gray-50 py-8">
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
        </div>
    );
};

export default FileUploaderExample;
