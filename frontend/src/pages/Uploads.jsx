import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { UploadCloud, FileSpreadsheet, Loader2, Trash2, FlaskConical, CheckCircle2, Link2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useApi, useAnalysis, errMsg } from "@/lib/api";
import { PageHeader, Panel, num, useLoadDemo } from "@/components/dialer/common";

const FIELDS = {
  calls: [
    ["list", "Lead list / campaign", true], ["timestamp", "Call date / time", true], ["disposition", "Disposition / status", true],
    ["phone", "Customer phone"], ["cli", "CLI / caller ID (if present)"], ["direction", "Direction (in/out)"], ["talk_time", "Talk time / duration"],
    ["call_id", "Call ID / uniqueid"], ["time", "Separate time column"], ["agent", "Agent"],
  ],
  cdr: [
    ["from", "Caller / source number", true], ["to", "Called / destination number", true], ["timestamp", "Call start time", true],
    ["call_id", "Call ID / uniqueid"], ["duration", "Duration / billsec"], ["time", "Separate time column"],
  ],
};
const ZONES = [["America/New_York", "US Eastern"], ["America/Chicago", "US Central"], ["America/Denver", "US Mountain"], ["America/Phoenix", "Arizona"], ["America/Los_Angeles", "US Pacific"], ["UTC", "UTC / GMT"], ["Asia/Kolkata", "India (IST)"], ["Asia/Karachi", "Pakistan (PKT)"], ["Asia/Manila", "Philippines"]];
const KINDS = [["calls", "Dialer call export", "Lists, dispositions, talk time"], ["cdr", "CDR report", "Adds the CLI to each call"]];
export const CATS = [["sale", "Completed sale"], ["contact", "Human contact"], ["connected", "Answered (machine)"], ["none", "Not connected"]];
const NONE = "__none__";

export const CatSelect = ({ value, onChange, testId }) => (
  <Select value={value} onValueChange={onChange}>
    <SelectTrigger className="h-7 w-[170px] text-xs" data-testid={testId}><SelectValue /></SelectTrigger>
    <SelectContent>{CATS.map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent>
  </Select>
);

const Mapper = ({ file, preview, onDone, onCancel }) => {
  const api = useApi();
  const [mapping, setMapping] = useState(preview.mapping);
  const [fileTz, setFileTz] = useState(preview.file_tz);
  const isCdr = preview.kind === "cdr";
  const [disps, setDisps] = useState(preview.dispositions);
  const [busy, setBusy] = useState(false);
  const setField = async (f, v) => {
    const col = v === NONE ? null : v;
    setMapping((m) => ({ ...m, [f]: col }));
    if (f === "disposition" && col) {
      const fd = new FormData(); fd.append("file", file); fd.append("column", col);
      setDisps(await api("post", "/uploads/dispositions", fd));
    }
  };
  const commit = async () => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("payload", JSON.stringify({ kind: preview.kind, file_tz: fileTz, mapping, disposition_map: Object.fromEntries(disps.map((d) => [d.name, d.category])) }));
      const u = await api("post", "/uploads/commit", fd);
      const dup = u.duplicates ? ` (${num(u.duplicates)} duplicates skipped)` : "";
      toast.success(isCdr ? `Imported ${num(u.rows_imported)} CDR rows${dup} — CLI found for ${num(u.cli_matched)} calls` : `Imported ${num(u.rows_imported)} calls${dup}${u.cli_matched ? ` — CLI matched for ${num(u.cli_matched)}` : ""}`);
      onDone();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <div className="space-y-4 fade-up" data-testid="mapping-step">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <FileSpreadsheet className="h-4 w-4 text-cyan-400" /><span className="text-slate-100">{preview.filename}</span>
        <span className="rounded bg-cyan-500/10 px-1.5 text-[10px] uppercase text-cyan-300">{isCdr ? "CDR" : "Call export"}</span>
        <span className="num text-slate-500">{num(preview.rows)} rows</span>
        {preview.known_format && <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 className="h-3.5 w-3.5" />Known format — mapping restored</span>}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="1 · Column mapping" subtitle="Match your Primo export columns">
          <div className="space-y-2">
            {FIELDS[preview.kind].map(([f, label, req]) => (
              <div key={f} className="flex items-center justify-between gap-3">
                <span className="text-xs text-slate-300">{label}{req && <span className="text-red-400"> *</span>}</span>
                <Select value={mapping[f] || NONE} onValueChange={(v) => setField(f, v)}>
                  <SelectTrigger className="h-7 w-[200px] text-xs" data-testid={`map-${f}`}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NONE}>— not in file —</SelectItem>
                    {preview.columns.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            ))}
            <div className="flex items-center justify-between gap-3 border-t border-[#172033] pt-2">
              <span className="text-xs text-slate-300">Times in this file are in</span>
              <Select value={fileTz} onValueChange={setFileTz}>
                <SelectTrigger className="h-7 w-[200px] text-xs" data-testid="map-file-tz"><SelectValue /></SelectTrigger>
                <SelectContent>{ZONES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
        </Panel>
        {isCdr ? <CdrHelp /> : <Panel title="2 · Disposition meaning" subtitle="Only 'Completed sale' counts as a conversion">
          <div className="scroll-thin max-h-[340px] space-y-1.5 overflow-y-auto pr-1">
            {disps.map((d, i) => (
              <div key={d.name} className="flex items-center justify-between gap-2">
                <span className="truncate text-xs text-slate-200">{d.name} <span className="num text-slate-500">{num(d.count)}</span></span>
                <CatSelect value={d.category} testId={`disp-cat-${i}`} onChange={(v) => setDisps((ds) => ds.map((x) => (x.name === d.name ? { ...x, category: v } : x)))} />
              </div>
            ))}
            {disps.length === 0 && <p className="text-xs text-slate-500">Map the disposition column to classify statuses.</p>}
          </div>
        </Panel>}
      </div>
      <div className="flex gap-2">
        <Button onClick={commit} disabled={busy} data-testid="import-commit-btn">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Import & analyse</Button>
        <Button variant="outline" onClick={onCancel} data-testid="import-cancel-btn">Cancel</Button>
      </div>
    </div>
  );
};

const CdrHelp = () => (
  <Panel title="2 · How CLIs are matched" testId="cdr-help">
    <ul className="space-y-2 text-xs text-slate-300">
      <li>• If both reports have a <span className="text-cyan-300">call ID / uniqueid</span>, calls are matched on it exactly.</li>
      <li>• Otherwise each dialer call is matched to the CDR leg with the <span className="text-cyan-300">same customer number</span> closest in time (within the window set in Settings, default ±2 min).</li>
      <li>• Outbound: the customer is the destination, so the caller number is your CLI. Inbound: the customer is the caller, so the dialled DID is your CLI.</li>
      <li>• Pick the right time zone — carrier CDRs are often in UTC while Primo exports use dialer time.</li>
      <li>• Upload order doesn't matter; calls without a match stay out of CLI stats.</li>
    </ul>
  </Panel>
);

const Coverage = () => {
  const api = useApi();
  const qc = useQueryClient();
  const { data } = useAnalysis();
  const [busy, setBusy] = useState(false);
  if (!data?.has_data) return null;
  const c = data.kpis.cli_coverage;
  const rematch = async () => {
    setBusy(true);
    try { const r = await api("post", "/cdr/rematch"); await qc.invalidateQueries(); toast.success(`Re-matched — CLI found for ${num(r.matched)} calls`); } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <div data-testid="cli-coverage" className={`flex flex-wrap items-center gap-3 rounded-md border px-4 py-3 text-xs ${c >= 80 ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-300" : "border-amber-500/30 bg-amber-500/5 text-amber-300"}`}>
      <Link2 className="h-4 w-4" />
      <span><span className="num font-semibold">{c}%</span> of calls in the selected window have a CLI.{c < 80 && " Upload the CDR report for the same dates to fill in the rest."}</span>
      <Button size="sm" variant="outline" className="ml-auto h-7" onClick={rematch} disabled={busy} data-testid="cdr-rematch-btn">{busy && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}Re-match CLIs</Button>
    </div>
  );
};

const History = () => {
  const api = useApi();
  const qc = useQueryClient();
  const { data = [] } = useQuery({ queryKey: ["uploads"], queryFn: () => api("get", "/uploads") });
  const remove = async (u) => {
    if (!window.confirm(`Remove "${u.filename}" and its ${u.rows_imported} calls?`)) return;
    try { await api("delete", `/uploads/${u.id}`); await qc.invalidateQueries(); toast.success("Upload removed"); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Panel title="Upload history" testId="upload-history">
      <div className="scroll-thin overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-[10px] uppercase tracking-wider text-slate-500 text-left"><tr><th className="py-1.5">File</th><th>Type</th><th>Uploaded</th><th>Call dates</th><th>Imported</th><th>Dupes</th><th>Lists</th><th>CLIs</th><th>CLI matched</th><th /></tr></thead>
          <tbody>
            {data.map((u, i) => (
              <tr key={u.id} className="border-t border-[#172033] text-slate-300" data-testid={`upload-row-${i}`}>
                <td className="py-2 text-slate-100">{u.filename}{u.is_demo && <span className="ml-2 rounded bg-amber-500/10 px-1.5 text-[10px] text-amber-400">SAMPLE</span>}</td>
                <td className="text-slate-400">{u.kind === "cdr" ? "CDR" : "Calls"}</td>
                <td className="num">{new Date(u.created_at).toLocaleDateString()}</td>
                <td className="num">{u.date_from.slice(0, 10)} → {u.date_to.slice(0, 10)}</td>
                <td className="num">{num(u.rows_imported)}</td><td className="num">{num(u.duplicates)}</td><td className="num">{u.kind === "cdr" ? "—" : u.lists}</td><td className="num">{u.clis}</td><td className="num">{u.cli_matched ? num(u.cli_matched) : "—"}</td>
                <td><Button variant="ghost" size="icon" onClick={() => remove(u)} data-testid={`upload-delete-btn-${i}`}><Trash2 className="h-3.5 w-3.5" /></Button></td>
              </tr>
            ))}
            {data.length === 0 && <tr><td colSpan={10} className="py-6 text-center text-slate-500">No uploads yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
};

export default function Uploads() {
  const api = useApi();
  const qc = useQueryClient();
  const input = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [kind, setKind] = useState("calls");
  const demo = useLoadDemo();
  const pick = async (f) => {
    if (!f) return;
    setBusy(true);
    try { const fd = new FormData(); fd.append("file", f); fd.append("kind", kind); setPreview(await api("post", "/uploads/preview", fd)); setFile(f); }
    catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  const reset = () => { setFile(null); setPreview(null); if (input.current) input.current.value = ""; };
  return (
    <div className="space-y-4">
      <PageHeader title="Report Upload" subtitle="Drop Primo call log / disposition exports. Duplicate calls across overlapping exports are skipped automatically.">
        <Button variant="outline" onClick={demo.run} disabled={demo.loading} data-testid="load-demo-btn">
          {demo.loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FlaskConical className="mr-2 h-4 w-4" />}Load sample data
        </Button>
      </PageHeader>
      <Coverage />
      {!preview && (
        <div className="grid gap-2 sm:grid-cols-2" data-testid="upload-kind-picker">
          {KINDS.map(([k, l, d]) => (
            <button key={k} onClick={() => setKind(k)} data-testid={`upload-kind-${k}`}
              className={`rounded-md border px-4 py-3 text-left transition-colors ${kind === k ? "border-cyan-400 bg-cyan-500/10" : "border-[#1F2B45] bg-[#0E131F] hover:border-cyan-500/40"}`}>
              <p className={`text-sm font-medium ${kind === k ? "text-cyan-300" : "text-slate-200"}`}>{l}</p>
              <p className="text-xs text-slate-500">{d}</p>
            </button>
          ))}
        </div>
      )}
      {preview ? <Mapper file={file} preview={preview} onCancel={reset} onDone={async () => { reset(); await qc.invalidateQueries(); }} /> : (
        <label data-testid="csv-upload-container"
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
          className={`grid-bg flex cursor-pointer flex-col items-center justify-center rounded-md border border-dashed py-16 transition-colors ${drag ? "border-cyan-400 bg-cyan-500/5" : "border-[#1F2B45] bg-[#0E131F] hover:border-cyan-500/50"}`}>
          {busy ? <Loader2 className="h-8 w-8 animate-spin text-cyan-400" /> : <UploadCloud className="h-8 w-8 text-cyan-400" />}
          <p className="mt-3 text-sm text-slate-200">{busy ? "Reading file…" : `Drag a ${kind === "cdr" ? "CDR" : "call export"} CSV / Excel here, or click to browse`}</p>
          <p className="mt-1 text-xs text-slate-500">{kind === "cdr" ? "Needs at least: caller number, called number, call start time" : "Needs at least: list/campaign, call date-time, disposition"}</p>
          <input ref={input} type="file" accept=".csv,.xlsx,.xls,.txt" className="hidden" onChange={(e) => pick(e.target.files[0])} data-testid="upload-file-input" />
        </label>
      )}
      <History />
    </div>
  );
}
