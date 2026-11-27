import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Pencil, Check, X, ShieldAlert, StickyNote, GraduationCap } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { useApi, errMsg } from "@/lib/api";
import { PageHeader } from "@/components/dialer/common";

const SECTIONS = [
  { type: "rule", title: "Operator rules", desc: "Hard rules the AI must always follow", icon: ShieldAlert, ph: "e.g. Never dial GA-AutoWarranty after 6pm EST" },
  { type: "note", title: "Business notes", desc: "Context about your operation", icon: StickyNote, ph: "e.g. We pay $0.06 per Medicare lead; inbound queue closes at 7pm" },
  { type: "learned", title: "Learned outcomes", desc: "What worked and what didn't — added automatically, editable", icon: GraduationCap, ph: "e.g. Resting CLIs for 72h restored answer rates" },
];

const Item = ({ m, i, onPatch, onDelete }) => {
  const [edit, setEdit] = useState(false);
  const [text, setText] = useState(m.text);
  return (
    <li data-testid={`memory-item-${m.type}-${i}`} className={`rounded border border-[#172033] bg-[#141B2D] p-3 transition-opacity ${m.active ? "" : "opacity-50"}`}>
      {edit ? (
        <div className="space-y-2">
          <Textarea value={text} onChange={(e) => setText(e.target.value)} className="text-xs" data-testid={`memory-edit-input-${m.type}-${i}`} />
          <div className="flex gap-1">
            <Button size="sm" onClick={() => { onPatch(m, { text }); setEdit(false); }} data-testid={`memory-save-btn-${m.type}-${i}`}><Check className="h-3.5 w-3.5" /></Button>
            <Button size="sm" variant="ghost" onClick={() => { setText(m.text); setEdit(false); }}><X className="h-3.5 w-3.5" /></Button>
          </div>
        </div>
      ) : <p className="text-sm text-slate-200">{m.text}</p>}
      <div className="mt-2 flex items-center gap-2 text-[10px] uppercase tracking-wider text-slate-500">
        <span>{m.source}</span><span className="num">{new Date(m.created_at).toLocaleDateString()}</span>
        <div className="ml-auto flex items-center gap-1">
          <Switch checked={m.active} onCheckedChange={(v) => onPatch(m, { active: v })} data-testid={`memory-toggle-${m.type}-${i}`} />
          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setEdit(true)} data-testid={`memory-edit-btn-${m.type}-${i}`}><Pencil className="h-3 w-3" /></Button>
          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => onDelete(m)} data-testid={`memory-delete-btn-${m.type}-${i}`}><Trash2 className="h-3 w-3" /></Button>
        </div>
      </div>
    </li>
  );
};

const Section = ({ s, items, onAdd, onPatch, onDelete }) => {
  const [text, setText] = useState("");
  const Icon = s.icon;
  return (
    <section className="rounded-md border border-[#1F2B45] bg-[#0E131F] p-4" data-testid={`memory-section-${s.type}`}>
      <div className="flex items-center gap-2"><Icon className="h-4 w-4 text-cyan-400" /><h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">{s.title}</h4><span className="num ml-auto text-xs text-slate-500">{items.length}</span></div>
      <p className="mt-1 text-xs text-slate-500">{s.desc}</p>
      <div className="mt-3 flex gap-2">
        <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={s.ph} rows={2} className="min-h-[44px] text-xs" data-testid={`memory-add-input-${s.type}`} />
        <Button onClick={() => { if (text.trim().length > 1) { onAdd(s.type, text); setText(""); } }} className="h-auto" data-testid={`memory-add-btn-${s.type}`}><Plus className="h-4 w-4" /></Button>
      </div>
      <ul className="mt-3 space-y-2">{items.map((m, i) => <Item key={m.id} m={m} i={i} onPatch={onPatch} onDelete={onDelete} />)}</ul>
    </section>
  );
};

export default function Memory() {
  const api = useApi();
  const qc = useQueryClient();
  const { data = [] } = useQuery({ queryKey: ["memory"], queryFn: () => api("get", "/memory") });
  const wrap = (fn, msg) => async (...a) => { try { await fn(...a); qc.invalidateQueries({ queryKey: ["memory"] }); if (msg) toast.success(msg); } catch (e) { toast.error(errMsg(e)); } };
  const onAdd = wrap((type, text) => api("post", "/memory", { type, text }), "Saved to AI memory");
  const onPatch = wrap((m, body) => api("patch", `/memory/${m.id}`, body));
  const onDelete = wrap((m) => api("delete", `/memory/${m.id}`), "Removed");
  return (
    <div>
      <PageHeader title="AI Memory" subtitle="Everything the AI knows about your business. Active items are used in every directive and chat answer; switch one off to make the AI ignore it." />
      <div className="grid gap-4 lg:grid-cols-3" data-testid="ai-memory-editor">
        {SECTIONS.map((s) => <Section key={s.type} s={s} items={data.filter((m) => m.type === s.type)} onAdd={onAdd} onPatch={onPatch} onDelete={onDelete} />)}
      </div>
    </div>
  );
}
