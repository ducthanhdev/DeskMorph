import React from "react";
import { Studio } from "./Studio";
import { Taskbar } from "./Taskbar";
import { DockContextMenuStandalone } from "./DockContextMenuStandalone";
import "./App.css";

export const App: React.FC = () => {
  const windowType = new URLSearchParams(window.location.search).get("window");

  if (windowType === "taskbar") {
    return <Taskbar />;
  }
  if (windowType === "dock-context-menu") {
    return <DockContextMenuStandalone />;
  }

  return <Studio />;
};

export default App;
