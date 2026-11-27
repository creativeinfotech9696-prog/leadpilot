import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles, Check, X, ThumbsDown, Loader2, RefreshCw, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useApi, useRecs, errMsg } from "@/lib/api";
import { PageHeader } from "@/components/dialer/common";

const FILTERS = [["active", "Active"], ["applied", "Applied"], ["ignored", "Ignored"], ["failed", "Didn't work"], ["all", "All"]];
const PRIO = { high: "text-red-400 border-red-500/30 bg-red-500/10", medium: "text-amber-400 border-amber-500/30 bg-amber-500/10", low: "text-slate-400 border-slate-500/30 bg-slate-500/10" };
const CAT = { lead_list: "Lead list", cli: "CLI", timing: "Timing", general: "General" };

const Outcome = ({ o }) => {
  if (!o) return <p className="text-xs text-slate-500">Outcome pending — upload the next report after applying and the AI will measure the impact.</p>;
  const I = o.verdict === "worked" ? TrendingUp : o.verdict === "worse" ? TrendingDown : Minus;
  const c = o.verdict === "worked" ? "text-emerald-400" : o.verdict === "worse" ? "text-red-400" : "text-slate-400";
  return (
    <p className={`num flex items-center gap-1.5 text-xs ${c}`} data-testid="rec-outcome"><I className="h-3.5 w-3.5" />
      {o.verdict.replace("_", " ")} · connect {o.before.connect_rate}% → {o.after.connect_rate}% · conv {o.before.conv_rate}% → {o.after.conv_rate}% ({o.scope})</p>
  );
};

const RecCard = ({ r, i, onFeedback }) => (
  <article data-testid={`rec-card-${i}`} className="fade-up rounded-md border border-[#1F2B45] bg-[#0E131F] p-4 transition-colors hover:border-cyan-500/30" style={{ animationDelay: `${i * 40}ms` }}>
    <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wider">
      <span className={`rounded border px-1.5 py-0.5 font-semibold ${PRIO[r.priority]}`}>{r.priority}</span>
      <span className="text-slate-500">{CAT[r.category]}</span>
      {r.target && <span className="num normal-case tracking-normal text-cyan-300">{r.target}</span>}
      <span className="ml-auto num text-slate-500">{r.confidence}% confidence</span>
    </div>
    <h3 className="mt-2 text-base font-semibold text-slate-100" data-testid={`rec-title-${i}`}>{r.title}</h3>
    <p className="mt-1.5 text-sm text-slate-300">{r.action}</p>
    <p className="mt-1.5 text-xs text-slate-400">{r.reason}</p>
    {r.evidence && <p className="num mt-2 inline-block rounded bg-[#141B2D] px-2 py-1 text-xs text-cyan-200">{r.evidence}</p>}
    <div className="mt-3 border-t border-[#172033] pt-3">
      {r.status === "new" ? (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => onFeedback(r, "applied")} data-testid={`rec-apply-btn-${i}`}><Check className="mr-1 h-3.5 w-3.5" />Applied</Button>
          <Button size="sm" variant="outline" onClick={() => onFeedback(r, "ignored")} data-testid={`rec-ignore-btn-${i}`}><X className="mr-1 h-3.5 w-3.5" />Ignore</Button>
          <Button size="sm" variant="outline" className="text-red-300" onClick={() => onFeedback(r, "failed")} data-testid={`rec-failed-btn-${i}`}><ThumbsDown className="mr-1 h-3.5 w-3.5" />Didn't work</Button>
        </div>
      ) : (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-xs"><span className="uppercase tracking-wider text-slate-500">Marked</span><span className="text-slate-200" data-testid={`rec-status-${i}`}>{r.status === "failed" ? "Didn't work" : r.status}</span>
            <button className="ml-auto text-slate-500 hover:text-slate-300 underline" onClick={() => onFeedback(r, "new", true)} data-testid={`rec-undo-btn-${i}`}>undo</button></div>
          {r.feedback_note && <p className="text-xs text-slate-400">“{r.feedback_note}”</p>}
          {r.status === "applied" && <Outcome o={r.outcome} />}
        </div>
      )}
    </div>
  </article>
);

export default function Directives() {
  const api = useApi();
  const qc = useQueryClient();
  const [filter, setFilter] = useState("active");
  const { data: recs = [], isLoading } = useRecs(filter);
  const { data: st } = useQuery({ queryKey: ["recs-status"], queryFn: () => api("get", "/recommendations/status"), refetchInterval: (q) => (q.state.data?.running ? 3000 : false) });
  const [pending, setPending] = useState(null);
  const [note, setNote] = useState("");

  useEffect(() => { if (st && !st.running) qc.invalidateQueries({ queryKey: ["recs"] }); }, [st?.running, st?.last_run, qc]); // eslint-disable-line

  const send = async (r, status, n = "") => {
    try {
      await api("patch", `/recommendations/${r.id}`, { status, note: n });
      toast.success(status === "applied" ? "Marked applied — impact will be measured on your next upload" : status === "failed" ? "Noted — the AI will learn from this" : "Updated");
      qc.invalidateQueries({ queryKey: ["recs"] });
      qc.invalidateQueries({ queryKey: ["memory"] });
    } catch (e) { toast.error(errMsg(e)); }
  };
  const onFeedback = (r, status, direct) => (direct || status === "applied" ? send(r, status) : (setNote(""), setPending({ r, status })));
  const generate = async () => {
    try { await api("post", "/recommendations/generate"); qc.invalidateQueries({ queryKey: ["recs-status"] }); toast("AI is analysing your floor…"); }
    catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div>
      <PageHeader title="AI Directives" subtitle="Daily action plan from your data, rules and past outcomes. Tell the AI what you did — it learns from every result.">
        {st?.last_run && <span className="num text-xs text-slate-500">Last run {new Date(st.last_run).toLocaleString()}</span>}
        <Button onClick={generate} disabled={st?.running} data-testid="generate-recs-btn">
          {st?.running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}{st?.running ? "Analysing…" : "Generate new plan"}
        </Button>
      </PageHeader>
      {st?.last_error && <p className="mb-4 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300" data-testid="recs-error">Last AI run failed: {st.last_error}</p>}
      <div className="mb-4 flex flex-wrap gap-1.5">
        {FILTERS.map(([k, l]) => (
          <button key={k} onClick={() => setFilter(k)} data-testid={`recs-filter-${k}`} className={`rounded border px-3 py-1 text-xs transition-colors ${filter === k ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-300" : "border-[#1F2B45] text-slate-400 hover:text-slate-200"}`}>{l}</button>
        ))}
      </div>
      <div className="grid gap-3 lg:grid-cols-2" data-testid="ai-recommendations-feed">
        {recs.map((r, i) => <RecCard key={r.id} r={r} i={i} onFeedback={onFeedback} />)}
      </div>
      {!isLoading && recs.length === 0 && (
        <div className="rounded-md border border-dashed border-[#1F2B45] py-14 text-center text-sm text-slate-500" data-testid="recs-empty">
          <Sparkles className="mx-auto mb-3 h-6 w-6 text-cyan-400" />{st?.running ? "The AI is building your plan…" : "No directives here. Generate a new plan or upload fresh data."}
        </div>
      )}
      <Dialog open={!!pending} onOpenChange={(o) => !o && setPending(null)}>
        <DialogContent className="border-[#1F2B45] bg-[#0E131F]">
          <DialogHeader><DialogTitle>{pending?.status === "failed" ? "What went wrong?" : "Why skip this?"}</DialogTitle></DialogHeader>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional — e.g. 'connects stayed flat', 'that list is reserved for inbound'" data-testid="rec-feedback-note" />
          <DialogFooter><Button onClick={() => { send(pending.r, pending.status, note); setPending(null); }} data-testid="rec-feedback-submit">Save feedback</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
