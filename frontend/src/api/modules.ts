export type ModuleName = "module-one" | "module-two";

export type ModuleOutput<TData = unknown> = {
  generatedAt: string;
  data: TData;
  text: string | null;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

export async function getModuleOutput<TData = unknown>(module: ModuleName): Promise<ModuleOutput<TData>> {
  const response = await fetch(`${apiBaseUrl}/api/v1/${module}/output`);

  if (!response.ok) {
    throw new Error(`${module} request failed: ${response.status}`);
  }

  return response.json() as Promise<ModuleOutput<TData>>;
}
