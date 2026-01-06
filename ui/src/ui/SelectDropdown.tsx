import { useState, useRef, useEffect } from 'react'
import { ChevronDown, Check } from 'lucide-react'

export default function SelectDropdown() {
  const [isOpen, setIsOpen] = useState(true)
  const [selectedOption, setSelectedOption] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const dropdownRef = useRef(null)
  const menuRef = useRef(null)
  const searchInputRef = useRef(null)

  const floatRef = useRef(null)

  const options = [
    { value: 'react', label: 'React' },
    { value: 'vue', label: 'Vue.js' },
    { value: 'angular', label: 'Angular' },
    { value: 'svelte', label: 'Svelte' },
    { value: 'nextjs', label: 'Next.js' },
    { value: 'nuxt', label: 'Nuxt.js' },
    { value: 'gatsby', label: 'Gatsby' },
    { value: 'remix', label: 'Remix' },
  ]

  // Filter options based on search term
  const filteredOptions = options.filter(option =>
    option.label.toLowerCase().includes(searchTerm.toLowerCase()),
  )

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false)
        setSearchTerm('')
      }
    }

    function handleMouseDblClick(event) {
      if (floatRef.current) {
        const ddrect = dropdownRef.current.getBoundingClientRect()
        const rect = floatRef.current.getBoundingClientRect()

        console.log('ddrect:', ddrect)
        console.log('flrect:', rect)

        floatRef.current.style.top = `${ddrect.clientY - 200}px`
        floatRef.current.style.left = `${ddrect.clientX}px`

        floatRef.current.style.position = 'fixed'
        floatRef.current.style.zIndex = '1000'
        floatRef.current.style.display = 'block'
        floatRef.current.style.width = '200px'
        floatRef.current.style.height = 'auto'
        floatRef.current.style.maxWidth = '200px'
        floatRef.current.style.maxHeight = '300px'
        floatRef.current.style.backgroundColor = 'lime'
        floatRef.current.style.border = '1px solid #ccc'

        //floatRef.current.innerHTML = menuRef.current.innerHTML; // Update floatRef content to match menuRef
      }
    }

    function handleMouseMove(event) {
      if (isOpen) {
        //floatRef.current.style.top = `${rect.y - rect.height}px`;
        //floatRef.current.style.left = `${rect.x}px`;
      }
    }

    const ddrect = dropdownRef.current.getBoundingClientRect()

    const floatRect = floatRef.current?.getBoundingClientRect()
    if (floatRect && floatRef.current) {
      console.log('ddrect:', ddrect)
      console.log('floatRect:', floatRect)
      floatRef.current.style.border = '2px solid red'
      floatRef.current.style.top = `${ddrect.y}px`
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('dblclick', handleMouseDblClick)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('dblclick', handleMouseDblClick)
    }
  }, [])

  // Focus search input when dropdown opens
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      searchInputRef.current.focus()
    }
  }, [isOpen])

  const toggleDropdown = (e) => {
    setIsOpen(!isOpen)
    if (!isOpen) {
      setSearchTerm('')
    }

    // get the current x,y position of the clicked element
    const rect = dropdownRef.current.getBoundingClientRect()
    console.log('ref rect:', rect)
    console.log('menu rect:', menuRef.current?.getBoundingClientRect())


    // floatRef.current.style.top = `${rect.y - rect.height}px`;
    // floatRef.current.style.left = `${rect.x}px`;
    // floatRef.current.style.position = 'absolute';
    // floatRef.current.style.zIndex = '1000';
    // floatRef.current.style.display = 'block';
    // floatRef.current.style.width = '200px';
    // floatRef.current.style.height = 'auto';
    // floatRef.current.style.maxWidth = '200px';
    // floatRef.current.style.maxHeight = '300px';
    // floatRef.current.style.backgroundColor = 'red';
    // floatRef.current.style.border = '1px solid #ccc';
    // console.log('floatRef rect:', floatRef.current?.getBoundingClientRect());

    // set the position of the menu to be above the clicked element
    // menuRef.current.style.top = `${rect.bottom + window.scrollY - rect.height - 300}px`;
    // menuRef.current.style.left = `${rect.left + window.scrollX}px`;
    // menuRef.current.style.position = 'fixed';
    // menuRef.current.style.zIndex = '1000';
    // menuRef.current.style.display = 'block';
    // menuRef.current.style.width = '200px';
    // menuRef.current.style.height = 'auto';
    // menuRef.current.style.maxWidth = '200px';
    // menuRef.current.style.maxHeight = '300px';
    // menuRef.current.style.backgroundColor = 'white';
    // menuRef.current.style.border = '1px solid #ccc';
    // menuRef.current.style.borderRadius = '0.375rem'; // Tailwind's rounded-md
    // menuRef.current.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.1)'; // Tailwind's shadow-sm
    // menuRef.current.style.padding = '0.5rem 0'; // Tailwind's py-2
    // menuRef.current.style.maxHeight = '15rem'; // Tailwind's max-h-60
    // menuRef.current.style.overflowY = 'auto'; // Tailwind's overflow-auto
    // menuRef.current.style.transition = 'all 0.2s ease-in-out'; // Tailwind's transition-all
  }

  const selectOption = (option) => {
    setSelectedOption(option)
    setIsOpen(false)
    setSearchTerm('')
  }

  const handleKeyDown = (event) => {
    if (event.key==='Escape') {
      setIsOpen(false)
      setSearchTerm('')
    }
  }

  return (
    <div className="w-full max-w-xs mx-auto p-8">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Choose a Framework
      </label>

      <div className="relative" ref={dropdownRef}>
        {/* Select Trigger */}
        <button
          onClick={toggleDropdown}
          className={`relative w-full bg-white border border-gray-300 rounded-md pl-3 pr-10 py-2 text-left cursor-default focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 sm:text-sm ${
            isOpen ? 'ring-1 ring-blue-500 border-blue-500':''
          }`}
        >
          <span className="block truncate">
            {selectedOption ? selectedOption.label:'Select an option...'}
          </span>
          <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
            <ChevronDown
              className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${
                isOpen ? 'rotate-180':''
              }`}
            />
          </span>
        </button>

        {/* Dropdown Options */}
        {isOpen && (
          <div ref={floatRef}>
            <div ref={menuRef}
                 className="absolute z-10 mt-1 w-full bg-white shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none sm:text-sm">
              {/* Search Input */}
              <div className="sticky top-0 bg-white px-3 py-2 border-b border-gray-100">
                <input
                  ref={searchInputRef}
                  type="text"
                  placeholder="Search options..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              {/* Options List */}
              <div className="max-h-48 overflow-auto">
                {filteredOptions.length > 0 ? (
                  filteredOptions.map((option) => (
                    <button
                      key={option.value}
                      onClick={() => selectOption(option)}
                      className={`relative cursor-default select-none py-2 pl-3 pr-9 w-full text-left hover:bg-blue-50 focus:outline-none focus:bg-blue-50 ${
                        selectedOption?.value===option.value
                          ? 'text-blue-600 bg-blue-50'
                          :'text-gray-900'
                      }`}
                    >
                    <span
                      className={`block truncate ${
                        selectedOption?.value===option.value ? 'font-medium':'font-normal'
                      }`}
                    >
                      {option.label}
                    </span>
                      {selectedOption?.value===option.value && (
                        <span className="absolute inset-y-0 right-0 flex items-center pr-4 text-blue-600">
                        <Check className="w-4 h-4" />
                      </span>
                      )}
                    </button>
                  ))
                ):(
                  <div className="px-3 py-2 text-sm text-gray-500">
                    No options found
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Selected Value Display */}
      {selectedOption && (
        <div className="mt-4 p-3 bg-gray-50 rounded-md">
          <p className="text-sm text-gray-600">
            Selected: <span className="font-medium text-gray-900">{selectedOption.label}</span>
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Value: {selectedOption.value}
          </p>
        </div>
      )}
    </div>
  )
}