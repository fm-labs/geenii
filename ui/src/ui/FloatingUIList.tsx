import { useState, useRef } from 'react';
import {
  useFloating,
  autoUpdate,
  offset,
  flip,
  shift,
  useClick,
  useDismiss,
  useRole,
  useInteractions,
  useListNavigation,
  FloatingPortal,
  FloatingFocusManager,
  FloatingList,
  useListItem,
} from '@floating-ui/react';
import { ChevronDown, User, Settings, LogOut, Bell, HelpCircle } from 'lucide-react';

// Individual list item component
function ListItem({ children, active, ...props }) {
  const { ref, index } = useListItem();

  return (
    <button
      ref={ref}
      role="option"
      aria-selected={active}
      tabIndex={active ? 0 : -1}
      className={`w-full px-4 py-2 text-left text-sm transition-colors duration-150 flex items-center gap-3 ${
        active
          ? 'bg-blue-50 text-blue-700 outline-none'
          : 'text-gray-700 hover:bg-gray-50'
      }`}
      {...props}
    >
      {children}
    </button>
  );
}

export default function FloatingUIList() {
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);

  const listRef = useRef([]);

  // Floating UI setup
  const { refs, floatingStyles, context } = useFloating({
    open: isOpen,
    onOpenChange: setIsOpen,
    middleware: [
      offset(4),
      flip({ padding: 10 }),
      shift({ padding: 10 })
    ],
    whileElementsMounted: autoUpdate,
  });

  // List navigation hook
  const listNavigation = useListNavigation(context, {
    listRef,
    activeIndex,
    onNavigate: setActiveIndex,
    virtual: true,
    loop: true,
  });

  // Interaction hooks
  const click = useClick(context);
  const dismiss = useDismiss(context);
  const role = useRole(context, { role: 'listbox' });

  const { getReferenceProps, getFloatingProps, getItemProps } = useInteractions([
    click,
    dismiss,
    role,
    listNavigation,
  ]);

  // Menu items data
  const menuItems = [
    {
      id: 'profile',
      label: 'View Profile',
      icon: User,
      action: () => console.log('Profile clicked')
    },
    {
      id: 'settings',
      label: 'Account Settings',
      icon: Settings,
      action: () => console.log('Settings clicked')
    },
    {
      id: 'notifications',
      label: 'Notifications',
      icon: Bell,
      action: () => console.log('Notifications clicked')
    },
    {
      id: 'help',
      label: 'Help & Support',
      icon: HelpCircle,
      action: () => console.log('Help clicked')
    },
    {
      id: 'logout',
      label: 'Sign Out',
      icon: LogOut,
      action: () => console.log('Logout clicked')
    }
  ];

  const handleItemClick = (item) => {
    setSelectedItem(item);
    item.action();
    setIsOpen(false);
  };

  return (
    <div className="w-auto">

      {/* Trigger Button */}
      <button
        ref={refs.setReference}
        className="inline-flex items-center justify-between w-full px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        {...getReferenceProps()}
      >
        <span className="flex items-center gap-2">
          <User className="w-4 h-4" />
          Account Menu
        </span>
        <ChevronDown
          className={`w-4 h-4 transition-transform duration-200 ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </button>

      {/* Floating Menu */}
      {isOpen && (
        <FloatingPortal>
          <FloatingFocusManager context={context} modal={false}>
            <div
              ref={refs.setFloating}
              style={floatingStyles}
              className="z-50 w-56 bg-white rounded-md shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none"
              {...getFloatingProps()}
            >
              <FloatingList elementsRef={listRef}>
                <div className="py-1" role="none">
                  {menuItems.map((item, index) => {
                    const IconComponent = item.icon;
                    return (
                      <ListItem
                        key={item.id}
                        active={activeIndex === index}
                        {...getItemProps({
                          onClick: () => handleItemClick(item),
                        })}
                      >
                        <IconComponent className="w-4 h-4" />
                        {item.label}
                      </ListItem>
                    );
                  })}
                </div>
              </FloatingList>
            </div>
          </FloatingFocusManager>
        </FloatingPortal>
      )}

      {/* Selected Item Display}
      {selectedItem && (
        <div className="mt-6 p-4 bg-blue-50 rounded-md border border-blue-200">
          <div className="flex items-center gap-2">
            <selectedItem.icon className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-medium text-blue-900">
              Last action: {selectedItem.label}
            </span>
          </div>
        </div>
      ) */}
    </div>
  );
}