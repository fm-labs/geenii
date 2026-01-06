import React from "react";
import Popup from "./Popup.tsx";

const PopupDemo = () => {
    const [isOpen, setIsOpen] = React.useState(false);
    const [popupSize, setPopupSize] = React.useState<any>("md");

    return (
        <div className="min-h-screen bg-gray-400 p-8">
            <div className="max-w-4xl mx-auto">
                <h1 className="text-3xl font-bold mb-8">React Popup Component Demo</h1>

                <div className="space-y-4 mb-8">
                    <div className="flex flex-wrap gap-4">
                        <button
                            onClick={() => setIsOpen(true)}
                            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                        >
                            Open Popup
                        </button>

                        <select
                            value={popupSize}
                            onChange={(e) => setPopupSize(e.target.value)}
                            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        >
                            <option value="sm">Small</option>
                            <option value="md">Medium</option>
                            <option value="lg">Large</option>
                            <option value="xl">Extra Large</option>
                            <option value="full">Full Width</option>
                        </select>
                    </div>
                </div>

                <Popup
                    show={isOpen}
                    onClose={() => setIsOpen(false)}
                    title="Example Popup"
                    size={popupSize}
                    showCloseButton={true}
                    closeOnOverlayClick={true}
                >
                    <div className="space-y-4">
                        <p className="text-gray-700">
                            This is a flexible popup component with smooth animations and customizable options.
                        </p>

                        <div className="bg-blue-50 p-4 rounded-lg">
                            <h3 className="font-semibold text-blue-900 mb-2">Usage Example:</h3>
                            <pre className="text-sm text-blue-800 overflow-x-auto">
{`<Popup
  isOpen={isOpen}
  onClose={() => setIsOpen(false)}
  title="My Popup"
  size="md"
  showCloseButton={true}
  closeOnOverlayClick={true}
>
  <p>Your content here!</p>
</Popup>`}
              </pre>
                        </div>

                        <div className="space-y-2">
                            <h3 className="font-semibold">Props:</h3>
                            <ul className="text-sm text-gray-600 space-y-1">
                                <li><strong>isOpen:</strong> boolean - Controls popup visibility</li>
                                <li><strong>onClose:</strong> function - Called when popup should close</li>
                                <li><strong>title:</strong> string - Optional header title</li>
                                <li><strong>size:</strong> 'sm' | 'md' | 'lg' | 'xl' | 'full' - Popup width</li>
                                <li><strong>showCloseButton:</strong> boolean - Show/hide close button</li>
                                <li><strong>closeOnOverlayClick:</strong> boolean - Close when clicking backdrop</li>
                                <li><strong>className:</strong> string - Additional CSS classes</li>
                            </ul>
                        </div>

                        <div className="flex gap-2 pt-4">
                            <button
                                onClick={() => setIsOpen(false)}
                                className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                            >
                                Close
                            </button>
                            <button
                                onClick={() => alert("Action clicked!")}
                                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                            >
                                Action Button
                            </button>
                        </div>
                    </div>
                </Popup>
            </div>
        </div>
    );
};
export default PopupDemo;
