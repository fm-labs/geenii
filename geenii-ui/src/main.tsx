import React from "react";
import ReactDOM from "react-dom/client";
import { isTauri } from '@tauri-apps/api/core'
import WebApp from "./web-app.tsx";
import DesktopApp from '@/desktop-app.tsx'

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    {isTauri() ? <DesktopApp /> : <WebApp />}
  </React.StrictMode>,
);
