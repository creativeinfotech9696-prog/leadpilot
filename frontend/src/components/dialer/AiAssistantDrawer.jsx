import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/react";
import { useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { X, Send, Trash2, Bot, Brain, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { API, useApi } from "@/lib/api";

const PROMPTS = [
  "Which lists should I load tomorrow morning?",
  "Which CLIs look spam-flagged right now?",
  "Best hours to dial my top list?",
  "Why are sales down vs last week?",
];

const Message = ({ m, i }) => (
  <div data-testid={`chat-message-${i}`} className={`fade-up ${m.role === "user" ? "ml-8" : "mr-2"}`}>
    {m.role === "user" ? (
      <div className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-sm text-slate-100 whitespace-pre-wrap">{m.content}</div>
    ) : (
      <div className="md text-sm leading-relaxed text-slate-300">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content || "…"}</ReactMarkdown>
      </div>
    )}
  </div>
);

export default function AiAssistantDrawer({ open, onClose }) {
  const api = useApi();
  const { getToken } = useAuth();
  const qc = useQueryClient();
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { if (open) api("get", "/chat/messages").then(setMsgs).catch(() => {}); }, [open, api]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const send = async (text) => {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    setInput("");
    setBusy(true);
    setMsgs((m) => [...m, { role: "user", content: message }, { role: "assistant", content: "" }]);
    const append = (d) => setMsgs((m) => { const c = [...m]; c[c.length - 1] = { ...c[c.length - 1], content: c[c.length - 1].content + d }; return c; });
    try {
      const res = await fetch(`${API}/chat/stream`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${await getToken()}` }, body: JSON.stringify({ message }) });
      if (!res.ok) throw new Error("AI request failed");
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop();
        for (const p of parts) {
          if (!p.startsWith("data: ")) continue;
          const ev = JSON.parse(p.slice(6));
          if (ev.delta) append(ev.delta);
          if (ev.error) toast.error(ev.error);
          if (ev.memory_saved?.length) { toast.success(`Saved to AI memory: ${ev.memory_saved[0]}`); qc.invalidateQueries({ queryKey: ["memory"] }); }
        }
      }
    } catch (e) { toast.error(e.message); }
    setBusy(false);
  };

  const clear = async () => { await api("delete", "/chat/messages"); setMsgs([]); };

  return (
    <aside data-testid="ai-chat-drawer" className={`fixed right-0 top-0 z-50 flex h-full w-full sm:w-[420px] flex-col border-l border-[#1F2B45] bg-[#0E131F] shadow-2xl transition-transform duration-300 ${open ? "translate-x-0" : "translate-x-full"}`}>
      <header className="flex h-14 items-center justify-between border-b border-[#1F2B45] px-4">
        <div className="flex items-center gap-2">
          <span className="relative flex h-7 w-7 items-center justify-center rounded border border-cyan-500/40 bg-cyan-500/10"><Bot className="h-4 w-4 text-cyan-400" /></span>
          <div>
            <p className="font-display text-sm font-bold text-slate-100">Dialer AI</p>
            <p className="text-[10px] uppercase tracking-wider text-slate-500 flex items-center gap-1"><span className="pulse-dot h-1.5 w-1.5 rounded-full bg-emerald-400" />grounded in your data</p>
          </div>
        </div>
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" onClick={clear} data-testid="ai-chat-clear-btn" title="Clear chat"><Trash2 className="h-4 w-4" /></Button>
          <Button variant="ghost" size="icon" onClick={onClose} data-testid="ai-chat-close-btn"><X className="h-4 w-4" /></Button>
        </div>
      </header>
      <div className="scroll-thin flex-1 space-y-4 overflow-y-auto p-4" data-testid="ai-chat-messages">
        {msgs.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-slate-400">Ask anything about your lists, CLIs, timing or results. Tell me your rules ("never dial list X after 6pm") and I'll remember them.</p>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-500"><Brain className="h-3.5 w-3.5" />Uses your AI memory and past outcomes</div>
          </div>
        )}
        {msgs.map((m, i) => <Message key={i} m={m} i={i} />)}
        {busy && msgs[msgs.length - 1]?.content === "" && <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />}
        <div ref={endRef} />
      </div>
      <div className="border-t border-[#1F2B45] p-3 space-y-2">
        <div className="scroll-thin flex gap-1.5 overflow-x-auto pb-1">
          {PROMPTS.map((p, i) => (
            <button key={p} onClick={() => send(p)} disabled={busy} data-testid={`ai-prompt-chip-${i}`}
              className="shrink-0 rounded-full border border-[#1F2B45] bg-[#141B2D] px-2.5 py-1 text-[11px] text-slate-300 transition-colors hover:border-cyan-500/50 hover:text-cyan-300">{p}</button>
          ))}
        </div>
        <div className="flex gap-2">
          <Textarea value={input} onChange={(e) => setInput(e.target.value)} rows={2} placeholder="Ask the dialer AI…" data-testid="ai-chat-input"
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} className="min-h-[44px] resize-none text-sm" />
          <Button onClick={() => send()} disabled={busy || !input.trim()} data-testid="ai-chat-send-btn" className="h-auto">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </aside>
  );
}
