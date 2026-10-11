import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { LangProvider } from "./i18n";
import { AppStateProvider } from "./state";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <LangProvider>
        <AppStateProvider>
          <App />
        </AppStateProvider>
      </LangProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
