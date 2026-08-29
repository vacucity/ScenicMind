import { AppLink } from "./AppLink";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <AppLink className={compact ? "product-brand compact" : "product-brand"} to="/dashboard" aria-label="智景 ScenicMind">
      <img src="/brand/logo-circle.png" alt="" />
      <span>
        <strong>智景</strong>
        <small>SCENICMIND</small>
      </span>
    </AppLink>
  );
}

