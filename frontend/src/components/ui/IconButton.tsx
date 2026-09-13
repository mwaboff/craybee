import type { ButtonHTMLAttributes } from "react";

import styles from "./IconButton.module.css";

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  "aria-label": string;
  variant?: "ghost" | "default";
};

export function IconButton({ variant = "default", className, ...rest }: IconButtonProps) {
  return (
    <button
      type="button"
      className={[styles.iconButton, variant === "ghost" ? styles.ghost : null, className]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    />
  );
}
