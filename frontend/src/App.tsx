import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";

export default function App() {
  return window.location.pathname === "/dashboard" ? (
    <DashboardPage />
  ) : (
    <LoginPage />
  );
}
