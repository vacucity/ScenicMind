import type { AnchorHTMLAttributes, MouseEvent } from "react";
import { navigate, type AppPath } from "../../app/navigation";

type AppLinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & {
  to: AppPath;
};

export function AppLink({ to, onClick, ...props }: AppLinkProps) {
  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    navigate(to);
  }

  return <a {...props} href={to} onClick={handleClick} />;
}

