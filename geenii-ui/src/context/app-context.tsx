import React from "react";
import { IDockerApiClient } from "../api/xai.types.ts";

// the API client lives in ApiContext (useApi())
type AppContextType = {
    isTauri: boolean;
    //dockerApi?: IDockerApiClient;
    apiHealth?: any;
    apiInfo?: any;
}

export const AppContext = React.createContext<AppContextType>(null)

