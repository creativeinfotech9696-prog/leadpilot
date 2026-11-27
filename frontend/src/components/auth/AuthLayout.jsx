import { Radar, Database, PhoneCall, Brain } from "lucide-react";

const POINTS = [
  { icon: Database, t: "Lead list health", d: "Know which data packages to run, rest or replace." },
  { icon: PhoneCall, t: "CLI reputation", d: "Catch spam-flagged caller IDs before they burn a shift." },
  { icon: Brain, t: "Learns your floor", d: "Every outcome you report sharpens the next call plan." },
];

export default function AuthLayout({ children }) {
  return (
    <div className="min-h-screen flex bg-[#090D14]">
      <div className="hidden lg:flex flex-col justify-between w-[46%] border-r border-[#1F2B45] grid-bg p-12">
        <div className="flex items-center gap-2 text-slate-100">
          <Radar className="h-5 w-5 text-cyan-400" />
          <span className="font-display font-bold text-lg tracking-tight">Dialer Intelligence</span>
        </div>
        <div className="fade-up">
          <p className="text-xs uppercase tracking-[0.25em] text-cyan-400 mb-4">Primo Dialer ops copilot</p>
          <h1 className="font-display text-4xl xl:text-5xl font-bold text-slate-50 leading-[1.05] max-w-md">
            Dial the right list, from the right number, at the right hour.
          </h1>
          <div className="mt-10 space-y-5">
            {POINTS.map(({ icon: Icon, t, d }) => (
              <div key={t} className="flex gap-3">
                <div className="h-8 w-8 shrink-0 rounded border border-[#1F2B45] bg-[#0E131F] flex items-center justify-center">
                  <Icon className="h-4 w-4 text-cyan-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-200">{t}</p>
                  <p className="text-sm text-slate-400">{d}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <p className="text-xs text-slate-500 font-mono">US outbound + inbound · completed-sale focused</p>
      </div>
      <div className="flex-1 flex items-center justify-center p-4">{children}</div>
    </div>
  );
}
