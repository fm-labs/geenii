import React from "react";
import { IAiClient, IDockerApiClient } from "../api/xai.types.ts";

type AppContextType = {
    isTauri: boolean;
    xaiApi: IAiClient;
    dockerApi?: IDockerApiClient
}

export const AppContext = React.createContext<AppContextType>(null)

