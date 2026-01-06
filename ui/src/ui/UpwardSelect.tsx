import { useState, useRef, useEffect } from 'react';
import { ChevronUp, Check } from 'lucide-react';

export default function UpwardSelect() {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedOption, setSelectedOption] = useState(null);
  const dropdownRef = useRef(null);

  const options = [
    { value: 'small', label: 'Small (1-10 employees)' },
    { value: 'medium', label: 'Medium (11-50 employees)' },
    { value: 'large', label: 'Large (51-200 employees)' },
    { value: 'enterprise', label: 'Enterprise (200+ employees)' },
    { value: 'startup', label: 'Startup' },
    { value: 'nonprofit', label: 'Non-profit' }
  ];

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const toggleDropdown = () => {
    setIsOpen(!isOpen);
  };

  const selectOption = (option) => {
    setSelectedOption(option);
    setIsOpen(false);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      setIsOpen(false);
    }
  };

  return (
    <div className="w-full max-w-sm mx-auto p-8 pt-64">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Company Size
      </label>

      <div className="relative" ref={dropdownRef}>
        {/* Dropdown Menu - Positioned Above */}
        {isOpen && (
          <div className="absolute bottom-full left-0 right-0 mb-1 bg-white shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none sm:text-sm z-10 border border-gray-200">
            {options.map((option) => (
              <button
                key={option.value}
                onClick={() => selectOption(option)}
                onKeyDown={handleKeyDown}
                className={`relative cursor-pointer select-none py-2 pl-3 pr-9 w-full text-left hover:bg-blue-50 focus:outline-none focus:bg-blue-50 transition-colors duration-150 ${
                  selectedOption?.value === option.value
                    ? 'text-blue-600 bg-blue-50'
                    : 'text-gray-900'
                }`}
              >
                <span
                  className={`block truncate ${
                    selectedOption?.value === option.value ? 'font-medium' : 'font-normal'
                  }`}
                >
                  {option.label}
                </span>
                {selectedOption?.value === option.value && (
                  <span className="absolute inset-y-0 right-0 flex items-center pr-4 text-blue-600">
                    <Check className="w-4 h-4" />
                  </span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Select Trigger */}
        <button
          onClick={toggleDropdown}
          className={`relative w-full bg-white border border-gray-300 rounded-md pl-3 pr-10 py-2 text-left cursor-default focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 sm:text-sm transition-colors duration-200 ${
            isOpen ? 'ring-1 ring-blue-500 border-blue-500' : 'hover:border-gray-400'
          }`}
        >
          <span className="block truncate">
            {selectedOption ? selectedOption.label : 'Select company size...'}
          </span>
          <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
            <ChevronUp
              className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${
                isOpen ? 'rotate-180' : ''
              }`}
            />
          </span>
        </button>
      </div>

      {/* Selected Value Display */}
      {selectedOption && (
        <div className="mt-4 p-3 bg-gray-50 rounded-md">
          <p className="text-sm text-gray-600">
            Selected: <span className="font-medium text-gray-900">{selectedOption.label}</span>
          </p>
        </div>
      )}
    </div>
  );
}