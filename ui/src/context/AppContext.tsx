import React from "react";
import { IAiClient, IDockerApiClient } from "../api/xai.types.ts";

type AppContextType = {
    isTauri: boolean;
    xaiApi: IAiClient;
    dockerApi?: IDockerApiClient;
    apiHealth?: any;
    apiInfo?: any;
}

export const AppContext = React.createContext<AppContextType>(null)

