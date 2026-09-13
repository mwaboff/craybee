import { Settings, SquarePen } from "lucide-react";
import { useState } from "react";

import logoUrl from "@/assets/craybee-logo.svg";
import { IconButton } from "@/components/ui/IconButton";
import { ChatPanel } from "@/features/chat/components/ChatPanel";
import { SettingsModal } from "@/features/settings/components/SettingsModal";

export default function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  // Bumping this remounts ChatPanel, which resets all of its state -- the
  // simplest way to start a new conversation with no dedicated reset code.
  const [chatKey, setChatKey] = useState(0);

  return (
    <div className="app">
      <header>
        <div className="brand">
          <img src={logoUrl} alt="" className="brand-mark" width={32} height={32} />
          <h1>craybee</h1>
        </div>
        <div className="header-actions">
          <IconButton
            variant="ghost"
            aria-label="New chat"
            onClick={() => setChatKey((key) => key + 1)}
          >
            <SquarePen size={18} />
          </IconButton>
          <IconButton variant="ghost" aria-label="Settings" onClick={() => setSettingsOpen(true)}>
            <Settings size={18} />
          </IconButton>
        </div>
      </header>

      <main>
        <ChatPanel key={chatKey} />
      </main>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
