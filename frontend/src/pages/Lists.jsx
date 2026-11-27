import { useAnalysis } from "@/lib/api";
import HealthTable from "@/components/dialer/HealthTable";
import { PageHeader, NoData, Loading, num, pct, hourLabel, DAYS } from "@/components/dialer/common";

const COLS = [
  { h: "Leads", v: (r) => num(r.leads) },
  { h: "Dials/lead", v: (r) => <span className={r.repeat >= 3 ? "text-red-400" : r.repeat >= 2 ? "text-amber-400" : ""}>{r.repeat.toFixed(1)}x</span> },
  { h: "Contact", v: (r) => pct(r.contact_rate) },
  { h: "Dials/sale", v: (r) => num(r.dials_per_sale || null) },
  { h: "Cost/sale", v: (r) => (r.cost_per_sale ? `$${r.cost_per_sale.toFixed(2)}` : "—") },
];

const Detail = (r) => (
  <div>
    <p className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">Best time to dial this list</p>
    {r.best_times.length === 0 ? <p className="text-xs text-slate-500">Not enough calls per hour yet.</p> : (
      <ul className="space-y-1 text-xs">
        {r.best_times.map((b) => (
          <li key={`${b.weekday}-${b.hour}`} className="num flex gap-4 text-slate-300">
            <span className="w-24 text-cyan-300">{DAYS[b.weekday]} {hourLabel(b.hour)}</span>
            <span>connect {pct(b.connect_rate)}</span><span>conv {pct(b.conv_rate, 2)}</span><span className="text-slate-500">{b.dials} dials</span>
          </li>
        ))}
      </ul>
    )}
  </div>
);

export default function Lists() {
  const { data, isLoading } = useAnalysis();
  if (isLoading) return <Loading />;
  return (
    <div>
      <PageHeader title="Lead List Health" subtitle="Every data package scored on connectivity, completed sales, wear-out and 3-day trend. Click a row for the reasoning." />
      {!data?.has_data ? <NoData /> : <HealthTable rows={data.lists} keyField="list" cols={COLS} renderDetail={Detail} testId="lead-health-table" label="List" />}
    </div>
  );
}
