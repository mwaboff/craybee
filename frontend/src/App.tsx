import logoUrl from "@/assets/craybee-logo.svg";
import { ChatPanel } from "@/features/chat/components/ChatPanel";

export default function App() {
  return (
    <div className="app">
      <header>
        <div className="brand">
          <img src={logoUrl} alt="" className="brand-mark" width={32} height={32} />
          <h1>craybee</h1>
        </div>
      </header>

      <main>
        <ChatPanel />
      </main>
    </div>
  );
}
