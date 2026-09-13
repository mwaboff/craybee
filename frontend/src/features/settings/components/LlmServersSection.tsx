import { Plus } from "lucide-react";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { HexLoader } from "@/components/ui/HexLoader";
import { useLlmServers } from "@/features/settings/hooks/useLlmServers";

import { LlmServerForm } from "./LlmServerForm";
import styles from "./LlmServersSection.module.css";

export function LlmServersSection() {
  const { data: servers, isLoading, isError, error } = useLlmServers();
  const [selectedId, setSelectedId] = useState<string | "new" | null>(null);
  const [dirty, setDirty] = useState(false);

  if (isLoading) return <HexLoader size="1.5em" />;
  if (isError) {
    return <Alert tone="error">{error instanceof Error ? error.message : "Failed to load servers."}</Alert>;
  }

  const list = servers ?? [];
  const defaultServer = list.find((s) => s.is_default);
  const selected =
    selectedId === "new"
      ? null
      : list.find((s) => s.id === selectedId) ?? defaultServer ?? list[0] ?? null;
  const isCreating = selectedId === "new" || (selectedId === null && list.length === 0);

  function guard(next: () => void) {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    next();
  }

  return (
    <section className={styles.section}>
      <h3>LLM Servers</h3>
      <p className={styles.description}>Connect and manage the language model servers craybee talks to.</p>

      <div className={styles.toolbar}>
        <label htmlFor="llm-server-select">Server</label>
        <select
          id="llm-server-select"
          value={isCreating ? "new" : selected?.id ?? ""}
          onChange={(e) => guard(() => setSelectedId(e.target.value))}
        >
          {isCreating && <option value="new" disabled>New server</option>}
          {list.map((server) => (
            <option key={server.id} value={server.id}>
              {server.name}
              {server.is_default ? " (default)" : ""}
            </option>
          ))}
        </select>
        <button type="button" onClick={() => guard(() => setSelectedId("new"))}>
          <Plus size={16} aria-hidden="true" /> New
        </button>
      </div>

      <LlmServerForm
        key={selected ? `${selected.id}:${selected.updated_at}` : "new"}
        server={selected}
        currentDefaultName={defaultServer?.name}
        onCreated={(s) => setSelectedId(s.id)}
        onDeleted={() => setSelectedId(null)}
        onDirtyChange={setDirty}
      />
    </section>
  );
}
