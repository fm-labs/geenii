import React from "react";
import { initWebXapi } from '@/init.ts'
import { IAiClient } from '@/api/xai.types.ts'
import { ServerContext } from '@/context/server-context.tsx'

type ApiContextType = {
    apiBaseUrl: string,
    //setApiBaseUrl: (url: string) => void,
    api: IAiClient,
    /** fetch() with relative paths resolved against apiBaseUrl */
    fetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>
    /** Like fetch, but throws on non-2xx responses and returns the parsed JSON body */
    fetchJson: (input: RequestInfo, init?: RequestInit) => Promise<any>
}

export const ApiContext = React.createContext<ApiContextType | undefined>(undefined);

export const ApiProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {

    const {serverUrl: apiBaseUrl} = React.useContext(ServerContext) // || {serverUrl: XAI_API_URL};
    //const [apiBaseUrl, setApiBaseUrl] = React.useState<string>(XAI_API_URL);
    const [api, setApi] = React.useState<IAiClient | null>(null);

    // relative paths (e.g. "/api/v1/info") are resolved against the api base url
    const resolve = React.useCallback((input: RequestInfo): RequestInfo => {
        if (typeof input !== 'string' || /^[a-z][a-z\d+.-]*:/i.test(input)) return input;
        return apiBaseUrl.replace(/\/+$/, '') + '/' + input.replace(/^\/+/, '');
    }, [apiBaseUrl]);

    const _fetch = React.useCallback(async (input: RequestInfo, init?: RequestInit) => {
        return await fetch(resolve(input), init);
    }, [resolve]);

    const _fetchJson = React.useCallback(async (input: RequestInfo, init?: RequestInit) => {
        const response = await fetch(resolve(input), init);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    }, [resolve]);

    // const initializeApi = React.useCallback(async () => {
    //   let xapiClient
    //   try {
    //     if (isTauri && FEATURE_TAURI_XAPI_ENABLED) {
    //       xapiClient = await initTauriXapi()
    //     } else {
    //       xapiClient = await initWebXapi(serverUrl)
    //     }
    //   } catch (error) {
    //     setBootLog(prev => [...prev, `❌ Error initializing api client: ${error.message}`])
    //     throw error;
    //   }
    //
    //   if (!xapiClient) {
    //     throw new Error('API client initialization failed.')
    //   }
    //   setApi(xapiClient)
    //   console.log('API client initialized with base url', serverUrl)
    // }, [serverUrl, setBootLog, setApi])

    // @ts-ignore
    // const isTauri = typeof window.__TAURI__!=='undefined'

    // const initXapiClient = async (serverUrl: string): Promise<IAiClient> => {
    //   if (isTauri && FEATURE_TAURI_XAPI_ENABLED) {
    //     return await initTauriXapi()
    //   } else {
    //     return await initWebXapi(serverUrl)
    //   }
    // }

    React.useEffect(() => {
        const initializeApi = async () => {
            try {
                const apiClient = await initWebXapi(apiBaseUrl);
                setApi(apiClient);
            } catch (error) {
                console.error("Failed to initialize API client:", error);
            }
        };

        initializeApi();
    }, [apiBaseUrl]);

    if (!api) {
        return <div>Loading API...</div>;
    }

    const contextValue: ApiContextType = {
        apiBaseUrl,
        //setApiBaseUrl,
        api,
        fetch: _fetch,
        fetchJson: _fetchJson
    };

    return (
        <ApiContext.Provider value={contextValue}>
            {children}
        </ApiContext.Provider>
    );
}


export const useApi = () => {
    const context = React.useContext(ApiContext);
    if (context === undefined) {
        throw new Error("useApi must be used within an ApiProvider");
    }
    return context;
}
