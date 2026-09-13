import { Server, X, type LucideIcon } from "lucide-react";
import { useState } from "react";

import { IconButton } from "@/components/ui/IconButton";
import { Modal } from "@/components/ui/Modal";

import { LlmServersSection } from "./LlmServersSection";
import styles from "./SettingsModal.module.css";

type Section = {
  id: string;
  label: string;
  icon: LucideIcon;
  Component: () => React.JSX.Element;
};

const SECTIONS = [
  { id: "llm-servers", label: "LLM Servers", icon: Server, Component: LlmServersSection },
] as const satisfies readonly Section[];

type Props = {
  open: boolean;
  onClose: () => void;
};

export function SettingsModal({ open, onClose }: Props) {
  const [activeId, setActiveId] = useState<string>(SECTIONS[0]!.id);
  const active = SECTIONS.find((section) => section.id === activeId) ?? SECTIONS[0]!;
  const ActiveComponent = active.Component;

  return (
    <Modal open={open} onClose={onClose} labelledBy="settings-title" className={styles.panel}>
      <div className={styles.header}>
        <h2 id="settings-title">Settings</h2>
        <IconButton aria-label="Close" onClick={onClose}>
          <X size={16} />
        </IconButton>
      </div>

      <div className={styles.body}>
        <nav className={styles.nav} aria-label="Settings sections">
          {SECTIONS.map((section) => {
            const Icon = section.icon;
            return (
              <button
                key={section.id}
                type="button"
                aria-current={section.id === activeId ? "page" : undefined}
                onClick={() => setActiveId(section.id)}
              >
                <Icon size={16} aria-hidden="true" />
                {section.label}
              </button>
            );
          })}
        </nav>

        <div className={styles.pane}>
          <ActiveComponent />
        </div>
      </div>
    </Modal>
  );
}
