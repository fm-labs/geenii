import React from "react";
import { IAiClient, IDockerApiClient } from "../api/xai.types.ts";

type AppContextType = {
    isTauri: boolean;
    api: IAiClient;
    //dockerApi?: IDockerApiClient;
    apiHealth?: any;
    apiInfo?: any;
}

export const AppContext = React.createContext<AppContextType>(null)

