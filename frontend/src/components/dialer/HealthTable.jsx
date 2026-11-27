import { Fragment, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { STATUS, StatusBadge, ScoreBar, Trend, pct, num } from "@/components/dialer/common";

export const StatusFilter = ({ value, onChange, rows }) => (
  <div className="flex flex-wrap gap-1.5">
    {["All", "Keep", "Watch", "Rest", "Replace"].map((s) => {
      const n = s === "All" ? rows.length : rows.filter((r) => r.status === s).length;
      return (
        <button key={s} onClick={() => onChange(s)} data-testid={`status-filter-${s.toLowerCase()}`}
          className={`rounded border px-2.5 py-1 text-xs transition-colors ${value === s ? (STATUS[s] || "border-cyan-500/40 bg-cyan-500/10 text-cyan-300") : "border-[#1F2B45] text-slate-400 hover:text-slate-200"}`}>
          {s} <span className="num opacity-70">{n}</span>
        </button>
      );
    })}
  </div>
);

// Generic health table used by lead lists and CLIs; `cols` define extra columns.
export default function HealthTable({ rows, keyField, cols, renderDetail, testId, label }) {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("All");
  const [open, setOpen] = useState(null);
  const shown = useMemo(() => rows.filter((r) => (status === "All" || r.status === status) && String(r[keyField]).toLowerCase().includes(q.toLowerCase())), [rows, q, status, keyField]);
  return (
    <div className="rounded-md border border-[#1F2B45] bg-[#0E131F]" data-testid={testId}>
      <div className="flex flex-col gap-3 border-b border-[#172033] p-3 sm:flex-row sm:items-center sm:justify-between">
        <StatusFilter value={status} onChange={setStatus} rows={rows} />
        <div className="relative sm:w-64">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Search ${label}…`} className="h-8 pl-8 text-xs" data-testid={`${testId}-search`} />
        </div>
      </div>
      <div className="scroll-thin overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#141B2D] text-[10px] uppercase tracking-wider text-slate-500">
            <tr>
              <th className="w-6 px-3 py-2" />
              <th className="px-3 py-2">{label}</th>
              {cols.map((c) => <th key={c.h} className="px-3 py-2 whitespace-nowrap">{c.h}</th>)}
              <th className="px-3 py-2">Dials</th><th className="px-3 py-2">Connect</th><th className="px-3 py-2 whitespace-nowrap">Prior → 3d</th>
              <th className="px-3 py-2">Sales</th><th className="px-3 py-2">Conv</th><th className="px-3 py-2">Score</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => {
              const k = r[keyField];
              const isOpen = open === k;
              return (
                <Fragment key={k}>
                  <tr onClick={() => setOpen(isOpen ? null : k)} data-testid={`${testId}-row-${i}`} className="cursor-pointer border-t border-[#172033] transition-colors hover:bg-[#141B2D]">
                    <td className="px-3 py-2.5 text-slate-500">{isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}</td>
                    <td className="px-3 py-2.5 font-medium text-slate-100 whitespace-nowrap">{k}</td>
                    {cols.map((c) => <td key={c.h} className="num px-3 py-2.5 text-slate-300 whitespace-nowrap">{c.v(r)}</td>)}
                    <td className="num px-3 py-2.5 text-slate-300">{num(r.dials)}</td>
                    <td className="num px-3 py-2.5 text-slate-200">{pct(r.connect_rate)}</td>
                    <td className="px-3 py-2.5 whitespace-nowrap"><Trend prior={r.prior_connect_rate} recent={r.recent_connect_rate} drop={r.connect_drop_pct} /></td>
                    <td className="num px-3 py-2.5 text-emerald-400">{num(r.sales)}</td>
                    <td className="num px-3 py-2.5 text-slate-200">{pct(r.conv_rate, 2)}</td>
                    <td className="px-3 py-2.5"><ScoreBar score={r.score} /></td>
                    <td className="px-3 py-2.5"><StatusBadge status={r.status} testId={`${testId}-status-${i}`} /></td>
                    <td className="px-3 py-2.5 text-slate-300 whitespace-nowrap">{r.action}</td>
                  </tr>
                  {isOpen && (
                    <tr className="bg-[#0B101A]"><td colSpan={cols.length + 10} className="px-6 py-4">
                      <div className="grid gap-4 md:grid-cols-2">
                        <div>
                          <p className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">Why this status</p>
                          <ul className="space-y-1 text-xs text-slate-300">{r.reasons.map((x) => <li key={x}>• {x}</li>)}</ul>
                        </div>
                        {renderDetail(r)}
                      </div>
                    </td></tr>
                  )}
                </Fragment>
              );
            })}
            {shown.length === 0 && <tr><td colSpan={cols.length + 10} className="px-3 py-8 text-center text-slate-500">Nothing matches this filter.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
