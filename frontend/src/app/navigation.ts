export type AppPath = "/login" | "/register" | "/upload" | "/dashboard";

export function navigate(path: AppPath, options: { replace?: boolean } = {}) {
  const method = options.replace ? "replaceState" : "pushState";
  window.history[method]({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

