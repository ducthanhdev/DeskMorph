import React, { useEffect } from "react";
import { useConfig } from "./config/store";
import { Studio } from "./Studio";
import { Taskbar } from "./Taskbar";
import { DockContextMenuStandalone } from "./DockContextMenuStandalone";
import { DockTooltip } from "./components/DockTooltip";
import { CalendarFlyout } from "./components/CalendarFlyout";
import "./App.css";

export const App: React.FC = () => {
  const { config } = useConfig();
  useEffect(() => { document.documentElement.lang = config.language; }, [config.language]);
  const windowType = new URLSearchParams(window.location.search).get("window");

  if (windowType === "dock-tooltip") return <DockTooltip />;

  if (windowType === "taskbar") {
    return <Taskbar />;
  }
  if (windowType === "dock-context-menu") {
    return <DockContextMenuStandalone />;
  }
  if (windowType === "calendar-flyout") {
    return <CalendarFlyout />;
  }

  return <Studio />;
};

export default App;
