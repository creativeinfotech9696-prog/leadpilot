import { useMemo, useState } from "react";
import { useAnalysis } from "@/lib/api";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, NoData, Loading, Panel, pct, hourLabel, DAYS } from "@/components/dialer/common";

const METRICS = { connect_rate: "Connect %", conv_rate: "Conversion %" };

export default function Timing() {
  const { data, isLoading } = useAnalysis();
  const [list, setList] = useState("__all__");
  const [metric, setMetric] = useState("connect_rate");
  const cells = useMemo(() => (data?.heatmap || []).filter((c) => c.list === list), [data, list]);
  if (isLoading) return <Loading />;
  if (!data?.has_data) return (<><PageHeader title="Best Time to Dial" /><NoData /></>);
  const hours = [...new Set(cells.map((c) => c.hour))].sort((a, b) => a - b);
  const map = Object.fromEntries(cells.map((c) => [`${c.weekday}-${c.hour}`, c]));
  const max = Math.max(...cells.filter((c) => c.dials >= 10).map((c) => c[metric]), 0.01);
  const top = [...cells].filter((c) => c.dials >= 15).sort((a, b) => b[metric] - a[metric]).slice(0, 6);
  return (
    <div>
      <PageHeader title="Best Time to Dial" subtitle={`Weekday × hour performance in ${data.timezone}. Brighter = better.`}>
        <Select value={list} onValueChange={setList}>
          <SelectTrigger className="h-8 w-[220px] text-xs" data-testid="heatmap-list-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All lists</SelectItem>
            {data.lists.map((l) => <SelectItem key={l.list} value={l.list}>{l.list}</SelectItem>)}
          </SelectContent>
        </Select>
        <div className="flex rounded border border-[#1F2B45]">
          {Object.entries(METRICS).map(([k, l]) => (
            <button key={k} onClick={() => setMetric(k)} data-testid={`heatmap-metric-${k}`} className={`px-3 py-1.5 text-xs transition-colors ${metric === k ? "bg-cyan-500/15 text-cyan-300" : "text-slate-400"}`}>{l}</button>
          ))}
        </div>
      </PageHeader>
      <div className="grid gap-4 xl:grid-cols-4">
        <Panel title="Heatmap" className="xl:col-span-3" testId="heatmap-time-to-dial">
          <div className="scroll-thin overflow-x-auto">
            <table className="border-separate border-spacing-1 text-[10px]">
              <thead><tr><th />{hours.map((h) => <th key={h} className="num px-1 font-normal text-slate-500">{hourLabel(h)}</th>)}</tr></thead>
              <tbody>
                {DAYS.map((d, wd) => (
                  <tr key={d}>
                    <td className="pr-2 text-slate-400">{d}</td>
                    {hours.map((h) => {
                      const c = map[`${wd}-${h}`];
                      const v = c && c.dials >= 10 ? c[metric] / max : 0;
                      return (
                        <td key={h} title={c ? `${d} ${hourLabel(h)} · ${c.dials} dials · connect ${pct(c.connect_rate)} · conv ${pct(c.conv_rate, 2)}` : "No calls"}
                          data-testid={`heat-cell-${wd}-${h}`} className="num h-9 min-w-[44px] rounded-sm text-center text-slate-100 transition-transform hover:scale-110"
                          style={{ background: c ? `rgba(6,182,212,${0.06 + v * 0.8})` : "#0B101A" }}>
                          {c && c.dials >= 10 ? c[metric].toFixed(metric === "conv_rate" ? 1 : 0) : ""}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
        <Panel title="Top windows" subtitle="Load this list in these slots" testId="top-windows-panel">
          <ol className="space-y-2.5">
            {top.map((c, i) => (
              <li key={i} className="flex items-center justify-between text-xs">
                <span className="text-slate-200"><span className="num mr-2 text-slate-500">{i + 1}</span>{DAYS[c.weekday]} {hourLabel(c.hour)}</span>
                <span className="num text-cyan-300">{pct(c[metric], metric === "conv_rate" ? 2 : 1)}</span>
              </li>
            ))}
            {top.length === 0 && <li className="text-xs text-slate-500">Not enough calls yet.</li>}
          </ol>
        </Panel>
      </div>
    </div>
  );
}
