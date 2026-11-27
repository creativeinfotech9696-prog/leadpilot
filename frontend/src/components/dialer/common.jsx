import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { UploadCloud, FlaskConical, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useApi, errMsg } from "@/lib/api";

export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const num = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 }));
export const pct = (n, d = 1) => (n == null ? "—" : `${Number(n).toFixed(d)}%`);
export const hourLabel = (h) => `${((h + 11) % 12) + 1}${h < 12 ? "am" : "pm"}`;

export const STATUS = {
  Keep: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  Watch: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  Rest: "text-orange-400 bg-orange-500/10 border-orange-500/30",
  Replace: "text-red-400 bg-red-500/10 border-red-500/30",
};

export const StatusBadge = ({ status, testId }) => (
  <span data-testid={testId} className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${STATUS[status] || STATUS.Watch}`}>
    <span className="h-1.5 w-1.5 rounded-full bg-current" />{status}
  </span>
);

export const Panel = ({ title, subtitle, actions, children, className = "", testId }) => (
  <section data-testid={testId} className={`rounded-md border border-[#1F2B45] bg-[#0E131F] ${className}`}>
    {(title || actions) && (
      <header className="flex items-start justify-between gap-3 border-b border-[#172033] px-4 py-3">
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</h4>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
        {actions}
      </header>
    )}
    <div className="p-4">{children}</div>
  </section>
);

export const Kpi = ({ label, value, sub, tone = "text-slate-50", testId, delay = 0 }) => (
  <div data-testid={testId} className="fade-up rounded-md border border-[#1F2B45] bg-[#0E131F] px-4 py-3 transition-colors duration-200 hover:border-cyan-500/40" style={{ animationDelay: `${delay}ms` }}>
    <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
    <p className={`num mt-1 text-2xl sm:text-3xl font-bold tracking-tight ${tone}`}>{value}</p>
    {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
  </div>
);

export const PageHeader = ({ title, subtitle, children }) => (
  <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <h1 data-testid="page-title" className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-slate-100">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
    </div>
    {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
  </div>
);

export const ScoreBar = ({ score }) => {
  const c = score >= 65 ? "bg-emerald-500" : score >= 45 ? "bg-amber-500" : score >= 30 ? "bg-orange-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-14 rounded-full bg-[#1B243B]"><div className={`h-1.5 rounded-full ${c}`} style={{ width: `${score}%` }} /></div>
      <span className="num text-xs text-slate-300">{score}</span>
    </div>
  );
};

export const Trend = ({ prior, recent, drop }) => {
  if (!prior) return <span className="text-xs text-slate-600">—</span>;
  const tone = drop >= 20 ? "text-red-400" : drop >= 10 ? "text-amber-400" : drop <= -5 ? "text-emerald-400" : "text-slate-400";
  return <span className={`num text-xs ${tone}`}>{pct(prior)} → {pct(recent)}</span>;
};

export function useLoadDemo() {
  const api = useApi();
  const qc = useQueryClient();
  const [loading, setLoading] = useState(false);
  const run = async () => {
    setLoading(true);
    try {
      await api("post", "/demo/load");
      await qc.invalidateQueries();
      toast.success("Sample data loaded — AI is preparing directives");
    } catch (e) { toast.error(errMsg(e)); }
    setLoading(false);
  };
  return { run, loading };
}

export function NoData() {
  const { run, loading } = useLoadDemo();
  return (
    <div data-testid="no-data-state" className="fade-up rounded-md border border-dashed border-[#1F2B45] bg-[#0E131F] grid-bg px-6 py-16 text-center">
      <UploadCloud className="mx-auto h-8 w-8 text-cyan-400" />
      <h2 className="font-display mt-4 text-xl font-bold text-slate-100">No dialer data yet</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">Upload a Primo call log / disposition export (CSV or Excel) to start the analysis, or explore with sample data first.</p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Button asChild data-testid="no-data-upload-btn"><Link to="/uploads"><UploadCloud className="mr-2 h-4 w-4" />Upload Primo report</Link></Button>
        <Button variant="outline" onClick={run} disabled={loading} data-testid="no-data-demo-btn">
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FlaskConical className="mr-2 h-4 w-4" />}Load sample data
        </Button>
      </div>
    </div>
  );
}

export const Loading = () => (
  <div data-testid="loading-state" className="flex items-center gap-2 py-20 justify-center text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin text-cyan-400" />Crunching dialer data…</div>
);
