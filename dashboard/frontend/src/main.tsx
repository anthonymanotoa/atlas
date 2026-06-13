import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// Apply saved theme before first paint (no flash).
document.documentElement.dataset.theme = localStorage.getItem("atlas-theme") || "dark";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
