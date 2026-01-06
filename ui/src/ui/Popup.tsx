import { useEffect, useState } from "react";
import { X } from "lucide-react";

export interface PopupProps {
    show: boolean;
    onClose: () => void;
    title?: string;
    children: React.ReactNode;
    size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
    showCloseButton?: boolean;
    closeOnOverlayClick?: boolean;
    className?: string;
}

const Popup = ({
                   show,
                   onClose,
                   title,
                   children,
                   size = 'md',
                   showCloseButton = true,
                   closeOnOverlayClick = true,
                   className = ''
               }: PopupProps) => {
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        if (show) {
            setIsVisible(true);
            document.body.style.overflow = 'hidden';
        } else {
            setIsVisible(false);
            document.body.style.overflow = 'unset';
        }

        return () => {
            document.body.style.overflow = 'unset';
        };
    }, [show]);

    const handleOverlayClick = (e) => {
        if (e.target === e.currentTarget && closeOnOverlayClick) {
            onClose();
        }
    };

    const handleEscapeKey = (e) => {
        if (e.key === 'Escape') {
            onClose();
        }
    };

    useEffect(() => {
        if (show) {
            document.addEventListener('keydown', handleEscapeKey);
            return () => document.removeEventListener('keydown', handleEscapeKey);
        }
    }, [show]);

    const sizeClasses = {
        sm: 'max-w-md',
        md: 'max-w-lg',
        lg: 'max-w-2xl',
        xl: 'max-w-4xl',
        full: 'max-w-[95vw]'
    };

    if (!isVisible) return null;

    return (
        <div
            className={`fixed inset-0 z-50 flex items-center justify-center p-4 ${
                show ? 'animate-in fade-in duration-200' : 'animate-out fade-out duration-200'
            }`}
            onClick={handleOverlayClick}
        >
            {/* Backdrop */}
            <div className="absolute inset-0 bg-black opacity-5 backdrop-blur-sm" />

            {/* Popup Content */}
            <div
                className={`relative w-full ${sizeClasses[size]} max-h-[90vh] bg-white rounded-lg shadow-xl dark:bg-black dark:opacity-95 ${
                    show ? 'animate-in zoom-in-95 duration-200' : 'animate-out zoom-out-95 duration-200'
                } ${className}`}
            >
                {/* Header */}
                {(title || showCloseButton) && (
                    <div className="flex items-center justify-between p-6 border-b border-gray-200">
                        {title && (
                            <h2 className="text-xl font-semibold text-gray-500">{title}</h2>
                        )}
                        {showCloseButton && (
                            <button
                                onClick={onClose}
                                className="p-1 rounded-full hover:bg-gray-100 transition-colors duration-200"
                                aria-label="Close popup"
                            >
                                <X className="w-5 h-5 text-gray-500" />
                            </button>
                        )}
                    </div>
                )}

                {/* Content */}
                <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
                    {children}
                </div>
            </div>
        </div>
    );
};

export default Popup;
