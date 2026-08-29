import { createContext, useContext } from "react";

import type { ModuleOneData, ModuleTwoReport } from "../api/modules";

export type DashboardData = {
  one: ModuleOneData;
  report: ModuleTwoReport;
  spots: string[];
  selectedSpot: string;
  setSelectedSpot: (spot: string) => void;
};

export const DashboardContext = createContext<DashboardData | null>(null);

export function useDashboard(): DashboardData {
  const value = useContext(DashboardContext);
  if (!value) {
    throw new Error("useDashboard 必须在 DashboardLayout 内使用");
  }
  return value;
}