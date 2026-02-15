import React, { createContext, useState } from 'react';

type TauriPanelContextType = {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
  body: React.ReactNode;
  setBody: (body: React.ReactNode) => void;
};

const TauriPanelContext = createContext<TauriPanelContextType | null>(null)

export const TauriPanelProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [body, setBody] = useState<React.ReactNode>(null);

  return (
    <TauriPanelContext.Provider value={{ isOpen, setIsOpen, body, setBody }}>
      {children}
    </TauriPanelContext.Provider>
  );
};

export const useTauriPanel = () => {
  const context = React.useContext(TauriPanelContext);
  if (!context) {
    throw new Error('useTauriPanel must be used within a TauriPanelProvider');
  }
  return context;
}


export default TauriPanelContext;