import "@fontsource/sora/500.css";
import "@fontsource/sora/600.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider, ThemeProvider, ToastProvider } from "./context/AppContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider><ToastProvider><AuthProvider><BrowserRouter><App /></BrowserRouter></AuthProvider></ToastProvider></ThemeProvider>
  </React.StrictMode>,
);
