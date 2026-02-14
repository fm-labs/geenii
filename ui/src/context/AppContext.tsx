import React from "react";
import { IAiClient, IDockerApiClient } from "../api/xai.types.ts";

type AppContextType = {
    isTauri: boolean;
    xaiApi: IAiClient;
    dockerApi?: IDockerApiClient;
    apiInfo?: any;
}

export const AppContext = React.createContext<AppContextType>(null)

