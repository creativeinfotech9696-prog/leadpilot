import { useState } from "react";
import { NavLink, Outlet, Link } from "react-router-dom";
import { UserButton } from "@clerk/react";
import { LayoutDashboard, Database, PhoneCall, Flame, Sparkles, UploadCloud, Brain, Sliders, Radar, Bot } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { WindowContext, useAnalysis } from "@/lib/api";
import AiAssistantDrawer from "@/components/dialer/AiAssistantDrawer";

const TABS = [
  { to: "/", label: "Command", icon: LayoutDashboard, id: "overview" },
  { to: "/lists", label: "Lead Lists", icon: Database, id: "lists" },
  { to: "/clis", label: "CLIs", icon: PhoneCall, id: "clis" },
  { to: "/timing", label: "Best Time", icon: Flame, id: "timing" },
  { to: "/directives", label: "AI Directives", icon: Sparkles, id: "directives" },
  { to: "/uploads", label: "Uploads", icon: UploadCloud, id: "uploads" },
  { to: "/memory", label: "AI Memory", icon: Brain, id: "memory" },
  { to: "/settings", label: "Settings", icon: Sliders, id: "settings" },
];

const DemoBanner = () => {
  const { data } = useAnalysis();
  if (!data?.demo_active) return null;
  return (
    <div data-testid="demo-banner" className="border-b border-amber-500/20 bg-amber-500/5 px-6 py-1.5 text-xs text-amber-300">
      You're viewing SAMPLE data. <Link to="/uploads" className="underline underline-offset-2">Upload your Primo report</Link> and remove the sample batch to see your real floor.
    </div>
  );
};

export default function Shell() {
  const [days, setDays] = useState(14);
  const [chatOpen, setChatOpen] = useState(false);
  return (
    <WindowContext.Provider value={{ days, setDays }}>
      <div className="min-h-screen bg-[#090D14]">
        <header className="sticky top-0 z-40 border-b border-[#1F2B45] bg-[#0E131F]/95 backdrop-blur-md">
          <div className="flex h-14 items-center justify-between gap-4 px-4 sm:px-6">
            <Link to="/" className="flex items-center gap-2 shrink-0" data-testid="brand-link">
              <Radar className="h-5 w-5 text-cyan-400" />
              <span className="font-display text-base font-bold tracking-tight text-slate-100 hidden sm:inline">Dialer Intelligence</span>
            </Link>
            <div className="flex items-center gap-2">
              <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
                <SelectTrigger className="h-8 w-[120px] text-xs" data-testid="window-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {[[7, "Last 7 days"], [14, "Last 14 days"], [30, "Last 30 days"], [0, "All data"]].map(([v, l]) => (
                    <SelectItem key={v} value={String(v)} data-testid={`window-option-${v}`}>{l}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button size="sm" onClick={() => setChatOpen((o) => !o)} data-testid="toggle-ai-chat-btn" className="h-8">
                <Bot className="mr-1.5 h-4 w-4" />Ask AI
              </Button>
              <UserButton />
            </div>
          </div>
          <nav className="scroll-thin flex gap-1 overflow-x-auto px-4 sm:px-6">
            {TABS.map(({ to, label, icon: Icon, id }) => (
              <NavLink key={to} to={to} end={to === "/"} data-testid={`nav-${id}`}
                className={({ isActive }) => `flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition-colors duration-200 ${isActive ? "border-cyan-400 text-cyan-300" : "border-transparent text-slate-400 hover:text-slate-200"}`}>
                <Icon className="h-3.5 w-3.5" />{label}
              </NavLink>
            ))}
          </nav>
        </header>
        <DemoBanner />
        <main className={`px-4 py-6 sm:px-6 lg:py-8 transition-[margin] duration-300 ${chatOpen ? "lg:mr-[420px]" : ""}`}>
          <Outlet />
        </main>
        <AiAssistantDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
      </div>
    </WindowContext.Provider>
  );
}
