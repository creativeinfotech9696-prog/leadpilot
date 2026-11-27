import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useApi, errMsg } from "@/lib/api";
import { PageHeader, Panel, Loading, num } from "@/components/dialer/common";
import { CatSelect } from "@/pages/Uploads";

const ZONES = [["America/New_York", "Eastern (ET)"], ["America/Chicago", "Central (CT)"], ["America/Denver", "Mountain (MT)"], ["America/Phoenix", "Arizona"], ["America/Los_Angeles", "Pacific (PT)"], ["Asia/Kolkata", "India (IST)"], ["Asia/Karachi", "Pakistan (PKT)"], ["Asia/Manila", "Philippines"], ["UTC", "UTC"]];

const NumField = ({ label, hint, value, onChange, testId }) => (
  <label className="block">
    <span className="text-xs text-slate-300">{label}</span>
    <Input type="number" value={value} onChange={(e) => onChange(Number(e.target.value))} className="num mt-1 h-8 text-xs" data-testid={testId} />
    <span className="mt-1 block text-[11px] text-slate-500">{hint}</span>
  </label>
);

export default function Settings() {
  const api = useApi();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["settings"], queryFn: () => api("get", "/settings") });
  const [f, setF] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) setF({ ...data, dmap: Object.fromEntries(data.dispositions.map((d) => [d.name, d.category])) }); }, [data]);
  if (isLoading || !f) return <Loading />;
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v }));
  const save = async () => {
    setBusy(true);
    try {
      await api("put", "/settings", { timezone: f.timezone, min_dials: f.min_dials, cli_drop_pct: f.cli_drop_pct, list_drop_pct: f.list_drop_pct, cdr_match_seconds: f.cdr_match_seconds, disposition_map: f.dmap, list_costs: f.list_costs });
      await qc.invalidateQueries();
      toast.success("Settings saved — analysis refreshed");
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <div className="space-y-4">
      <PageHeader title="Settings" subtitle="Tune how the AI reads your dialer.">
        <Button onClick={save} disabled={busy} data-testid="settings-save-btn">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}Save settings</Button>
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Time zone & thresholds" testId="settings-thresholds">
          <div className="space-y-4">
            <label className="block">
              <span className="text-xs text-slate-300">Reporting time zone</span>
              <Select value={f.timezone} onValueChange={set("timezone")}>
                <SelectTrigger className="mt-1 h-8 text-xs" data-testid="settings-timezone"><SelectValue /></SelectTrigger>
                <SelectContent>{ZONES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
              </Select>
              <span className="mt-1 block text-[11px] text-slate-500">Also used to read timestamps in new uploads</span>
            </label>
            <NumField label="Minimum dials before judging" hint="Lists / CLIs below this stay on Watch" value={f.min_dials} onChange={set("min_dials")} testId="settings-min-dials" />
            <NumField label="CLI spam-flag drop (%)" hint="3-day answer-rate drop that rests a CLI" value={f.cli_drop_pct} onChange={set("cli_drop_pct")} testId="settings-cli-drop" />
            <NumField label="CDR match window (seconds)" hint="How far apart dialer and CDR times may be for the same call (±)" value={f.cdr_match_seconds} onChange={set("cdr_match_seconds")} testId="settings-cdr-window" />
            <NumField label="List exhaustion drop (%)" hint="Connect drop that, with heavy redials, replaces a list" value={f.list_drop_pct} onChange={set("list_drop_pct")} testId="settings-list-drop" />
          </div>
        </Panel>
        <Panel title="Disposition meaning" subtitle="Only 'Completed sale' counts as conversion" testId="settings-dispositions">
          <div className="scroll-thin max-h-[420px] space-y-1.5 overflow-y-auto pr-1">
            {f.dispositions.map((d, i) => (
              <div key={d.name} className="flex items-center justify-between gap-2">
                <span className="truncate text-xs text-slate-200">{d.name} <span className="num text-slate-500">{num(d.count)}</span></span>
                <CatSelect value={f.dmap[d.name]} testId={`settings-disp-${i}`} onChange={(v) => setF((x) => ({ ...x, dmap: { ...x.dmap, [d.name]: v } }))} />
              </div>
            ))}
            {f.dispositions.length === 0 && <p className="text-xs text-slate-500">Dispositions appear here after your first upload.</p>}
          </div>
        </Panel>
        <Panel title="Lead list cost" subtitle="Total spend per list ($) → cost per sale" testId="settings-list-costs">
          <div className="scroll-thin max-h-[420px] space-y-1.5 overflow-y-auto pr-1">
            {f.lists.map((l, i) => (
              <div key={l} className="flex items-center justify-between gap-2">
                <span className="truncate text-xs text-slate-200">{l}</span>
                <Input type="number" min="0" placeholder="$" value={f.list_costs[l] ?? ""} className="num h-7 w-28 text-xs" data-testid={`settings-cost-${i}`}
                  onChange={(e) => setF((x) => ({ ...x, list_costs: { ...x.list_costs, [l]: e.target.value === "" ? 0 : Number(e.target.value) } }))} />
              </div>
            ))}
            {f.lists.length === 0 && <p className="text-xs text-slate-500">Lists appear here after your first upload.</p>}
          </div>
        </Panel>
      </div>
    </div>
  );
}
