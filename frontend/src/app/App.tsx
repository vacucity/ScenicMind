import { useEffect, useState } from "react";
import { AuthPage } from "../features/auth/pages/AuthPage";
import { getSession } from "../features/auth/services/session";
import { DashboardPage } from "../features/dashboard/pages/DashboardPage";
import { UploadPage } from "../features/upload/pages/UploadPage";
import { navigate, type AppPath } from "./navigation";

const knownPaths: AppPath[] = ["/login", "/register", "/upload", "/dashboard"];
const protectedPaths: AppPath[] = ["/upload", "/dashboard"];

export default function App() {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const syncPath = () => setPath(window.location.pathname);
    window.addEventListener("popstate", syncPath);
    return () => window.removeEventListener("popstate", syncPath);
  }, []);

  const route: AppPath = knownPaths.includes(path as AppPath) ? path as AppPath : "/login";
  const hasSession = Boolean(getSession());

  useEffect(() => {
    if (path !== route) navigate(route, { replace: true });
    else if (protectedPaths.includes(route) && !hasSession) navigate("/login", { replace: true });
    else if ((route === "/login" || route === "/register") && hasSession) navigate("/upload", { replace: true });
  }, [hasSession, path, route]);

  if (protectedPaths.includes(route) && !hasSession) return <AuthPage key="login" mode="login" />;
  if ((route === "/login" || route === "/register") && hasSession) return <UploadPage />;

  switch (route) {
    case "/register": return <AuthPage key="register" mode="register" />;
    case "/upload": return <UploadPage />;
    case "/dashboard": return <DashboardPage />;
    default: return <AuthPage key="login" mode="login" />;
  }
}
