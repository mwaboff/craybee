import { CircleAlert, CircleCheck, Info, X } from "lucide-react";
import type { ReactNode } from "react";

import { IconButton } from "./IconButton";
import styles from "./Alert.module.css";

type AlertProps = {
  tone: "error" | "success" | "info";
  children: ReactNode;
  onDismiss?: () => void;
  className?: string;
};

const ICONS = {
  error: CircleAlert,
  success: CircleCheck,
  info: Info,
};

export function Alert({ tone, children, onDismiss, className }: AlertProps) {
  const Icon = ICONS[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={[styles.alert, styles[tone], className].filter(Boolean).join(" ")}
    >
      <Icon size={16} aria-hidden="true" />
      <div className={styles.content}>{children}</div>
      {onDismiss && (
        <IconButton variant="ghost" aria-label="Dismiss" onClick={onDismiss} className={styles.dismiss}>
          <X size={16} aria-hidden="true" />
        </IconButton>
      )}
    </div>
  );
}
