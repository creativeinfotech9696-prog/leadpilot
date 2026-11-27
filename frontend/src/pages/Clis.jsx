import { useAnalysis } from "@/lib/api";
import HealthTable from "@/components/dialer/HealthTable";
import { PageHeader, NoData, Loading, Panel, pct, num } from "@/components/dialer/common";

const COLS = [
  { h: "Area", v: (r) => r.area_code || "—" },
  { h: "Recent dials", v: (r) => num(r.recent_dials) },
];

const Detail = (r) => (
  <div>
    <p className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">Works best with</p>
    {r.top_lists.length ? <ul className="space-y-1 text-xs text-cyan-300">{r.top_lists.map((l) => <li key={l}>• {l}</li>)}</ul> : <p className="text-xs text-slate-500">Not enough paired volume yet.</p>}
  </div>
);

export default function Clis() {
  const { data, isLoading } = useAnalysis();
  if (isLoading) return <Loading />;
  return (
    <div>
      <PageHeader title="CLI Health & Reputation" subtitle="A sudden drop in answer rate over the last 3 days usually means carriers are labelling the number as spam." />
      {!data?.has_data ? <NoData /> : (
        <div className="space-y-4">
          <HealthTable rows={data.clis} keyField="cli" cols={COLS} renderDetail={Detail} testId="cli-health-table" label="CLI" />
          <Panel title="Best CLI + list pairings" subtitle="Highest-converting caller ID and list combinations in this window" testId="cli-pairs-panel">
            <div className="scroll-thin overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-[10px] uppercase tracking-wider text-slate-500"><tr><th className="py-1.5 text-left">CLI</th><th className="text-left">List</th><th>Dials</th><th>Connect</th><th>Conv</th></tr></thead>
                <tbody className="num">
                  {data.pairs.slice(0, 10).map((p, i) => (
                    <tr key={i} className="border-t border-[#172033] text-slate-300" data-testid={`cli-pair-row-${i}`}>
                      <td className="py-2 text-slate-100">{p.cli}</td><td className="font-sans">{p.list}</td>
                      <td className="text-center">{num(p.dials)}</td><td className="text-center">{pct(p.connect_rate)}</td><td className="text-center text-emerald-400">{pct(p.conv_rate, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}
