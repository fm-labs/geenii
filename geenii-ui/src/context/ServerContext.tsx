import React from "react";

type ServerContextType = {
    //isConnected?: boolean;
    //setIsConnected: (isConnected: boolean) => void;
    serverUrl?: string;
    setServerUrl: (serverUrl: string) => void;
}

export const ServerContext = React.createContext<ServerContextType>(null)

