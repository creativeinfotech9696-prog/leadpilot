import { Link } from "react-router-dom";
import { ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, CartesianGrid, AreaChart, Area } from "recharts";
import { ArrowRight, Sparkles } from "lucide-react";
import { useAnalysis, useRecs } from "@/lib/api";
import { Kpi, Panel, PageHeader, NoData, Loading, StatusBadge, num, pct, hourLabel, DAYS } from "@/components/dialer/common";

const TT = { contentStyle: { background: "#141B2D", border: "1px solid #1F2B45", borderRadius: 6, fontSize: 12 }, labelStyle: { color: "#94A3B8" } };
const AX = { stroke: "#475569", fontSize: 11, tickLine: false, axisLine: false };

const DailyChart = ({ data }) => (
  <ResponsiveContainer width="100%" height={240}>
    <ComposedChart data={data}>
      <CartesianGrid stroke="#172033" vertical={false} />
      <XAxis dataKey="date" {...AX} tickFormatter={(d) => d.slice(5)} />
      <YAxis yAxisId="l" {...AX} />
      <YAxis yAxisId="r" orientation="right" {...AX} unit="%" />
      <Tooltip {...TT} />
      <Bar yAxisId="l" dataKey="dials" fill="#1F2B45" radius={[2, 2, 0, 0]} name="Dials" />
      <Line yAxisId="r" dataKey="connect_rate" stroke="#06B6D4" strokeWidth={2} dot={false} name="Connect %" />
      <Line yAxisId="r" dataKey="conv_rate" stroke="#10B981" strokeWidth={2} dot={false} name="Conversion %" />
    </ComposedChart>
  </ResponsiveContainer>
);

const HourlyChart = ({ data }) => (
  <ResponsiveContainer width="100%" height={240}>
    <AreaChart data={data}>
      <defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#06B6D4" stopOpacity={0.35} /><stop offset="100%" stopColor="#06B6D4" stopOpacity={0} /></linearGradient></defs>
      <CartesianGrid stroke="#172033" vertical={false} />
      <XAxis dataKey="hour" {...AX} tickFormatter={hourLabel} />
      <YAxis {...AX} unit="%" />
      <Tooltip {...TT} labelFormatter={hourLabel} />
      <Area dataKey="connect_rate" stroke="#06B6D4" fill="url(#cg)" strokeWidth={2} name="Connect %" />
      <Area dataKey="conv_rate" stroke="#10B981" fill="transparent" strokeWidth={2} name="Conversion %" />
    </AreaChart>
  </ResponsiveContainer>
);

const TopRecs = () => {
  const { data = [] } = useRecs("active");
  return (
    <Panel title="Today's AI directives" testId="overview-directives" actions={<Link to="/directives" className="text-xs text-cyan-400 hover:underline flex items-center gap-1" data-testid="overview-all-directives-link">All <ArrowRight className="h-3 w-3" /></Link>}>
      {data.length === 0 ? <p className="text-sm text-slate-500">AI is preparing directives… check the AI Directives tab in a moment.</p> : (
        <ul className="space-y-3">
          {data.slice(0, 4).map((r) => (
            <li key={r.id} className="flex gap-2"><Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyan-400" />
              <div><p className="text-sm text-slate-200">{r.title}</p><p className="num text-xs text-slate-500">{r.evidence}</p></div></li>
          ))}
        </ul>
      )}
    </Panel>
  );
};

const ListGlance = ({ lists }) => (
  <Panel title="Lead lists at a glance" testId="overview-lists" actions={<Link to="/lists" className="text-xs text-cyan-400 hover:underline">Details</Link>}>
    <div className="space-y-2">
      {[...lists].sort((a, b) => b.score - a.score).slice(0, 8).map((l) => (
        <div key={l.list} className="flex items-center justify-between gap-2 text-sm">
          <span className="truncate text-slate-300">{l.list}</span>
          <div className="flex items-center gap-3 shrink-0"><span className="num text-xs text-slate-400">{pct(l.conv_rate, 2)}</span><StatusBadge status={l.status} /></div>
        </div>
      ))}
    </div>
  </Panel>
);

export default function Overview() {
  const { data, isLoading } = useAnalysis();
  if (isLoading) return <Loading />;
  if (!data?.has_data) return (<><PageHeader title="Operations Command" subtitle="Your Primo Dialer floor at a glance" /><NoData /></>);
  const k = data.kpis;
  const best = data.best_overall?.[0];
  return (
    <div>
      <PageHeader title="Operations Command" subtitle={`Data ${data.start.slice(0, 10)} → ${data.anchor.slice(0, 10)} · ${data.timezone}`} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Kpi testId="kpi-total-dials" label="Dials" value={num(k.dials)} sub={`${num(k.outbound)} out · ${num(k.inbound)} in`} />
        <Kpi testId="kpi-connect-rate" label="Connect rate" value={pct(k.connect_rate)} sub={`${num(k.connects)} answered`} tone="text-cyan-300" delay={50} />
        <Kpi testId="kpi-contact-rate" label="Contact rate" value={pct(k.contact_rate)} sub={`${num(k.contacts)} human talks`} delay={100} />
        <Kpi testId="kpi-conversions" label="Completed sales" value={num(k.sales)} sub={`${num(k.dials_per_sale)} dials / sale`} tone="text-emerald-400" delay={150} />
        <Kpi testId="kpi-conversion-rate" label="Conversion" value={pct(k.conv_rate, 2)} sub="sales ÷ dials" tone="text-emerald-400" delay={200} />
        <Kpi testId="kpi-cli-at-risk" label="At-risk" value={`${k.flagged_clis} / ${k.lists_to_replace}`} sub="CLIs / lists to rest" tone={k.flagged_clis + k.lists_to_replace ? "text-orange-400" : "text-slate-50"} delay={250} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Panel title="Daily volume & rates" className="lg:col-span-2" testId="chart-daily-trend"><DailyChart data={data.daily} /></Panel>
        <TopRecs />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Panel title="Connect & conversion by hour" subtitle={best ? `Peak window: ${DAYS[best.weekday]} ${hourLabel(best.hour)} — ${pct(best.connect_rate)} connect, ${pct(best.conv_rate, 2)} conv` : null} className="lg:col-span-2" testId="chart-hourly-trend"><HourlyChart data={data.hourly} /></Panel>
        <ListGlance lists={data.lists} />
      </div>
      <Panel title="Outbound vs inbound" className="mt-4" testId="chart-inbound-outbound">
        <div className="grid gap-3 sm:grid-cols-2">
          {data.direction.map((d) => (
            <div key={d.direction} className="rounded border border-[#172033] bg-[#141B2D] p-3" data-testid={`direction-${d.direction}`}>
              <p className="text-xs uppercase tracking-wider text-slate-500">{d.direction}</p>
              <div className="num mt-2 grid grid-cols-4 gap-2 text-sm text-slate-200">
                <div><p className="text-[10px] text-slate-500">Calls</p>{num(d.dials)}</div>
                <div><p className="text-[10px] text-slate-500">Connect</p>{pct(d.connect_rate)}</div>
                <div><p className="text-[10px] text-slate-500">Sales</p>{num(d.sales)}</div>
                <div><p className="text-[10px] text-slate-500">Conv</p>{pct(d.conv_rate, 2)}</div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
