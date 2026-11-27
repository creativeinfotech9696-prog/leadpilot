# Dialer Intelligence — PRD

## Original problem
I use Primo Dialer for a US calling business with multiple CLIs and multiple lead lists (data packages), outbound + inbound. I want a highly intelligent, adaptive AI platform that analyzes the dialer in detail and suggests which leads to use when and which to change when, based on response, connectivity and conversions, and that gets more efficient with experience.

## Architecture
- FastAPI + MongoDB backend: `server.py` (routes), `analytics.py` (pandas metrics, health scores, trends, heatmap, outcome comparison), `ingest.py` (CSV/Excel parsing, auto column mapping, dedupe keys), `ai.py` (Claude Sonnet 5.5 via Emergent LLM key: context builder, recommendations, streaming chat), `demo.py` (sample data generator), `clerk_auth.py` (Emergent-managed Clerk).
- React frontend: Shell with tabs + window selector + AI chat drawer; pages Overview, Lists, Clis, Timing, Directives, Uploads, Memory, Settings.
- Uploads are stateless: the browser sends the file to preview, then sends it again with the mapping to commit (nothing is stored on the pod).

## Personas
Owner / operations manager; floor managers.

## Implemented (2026-11-27) — Phase 1 MVP
- Email/password sign-in (Clerk), one shared workspace
- Upload Primo CSV/Excel, auto column mapping that is remembered per file format, disposition categories (sale/contact/connected/none), dedupe, upload history + delete, sample data loader
- Dashboard KPIs, daily/hourly charts, outbound vs inbound, 7/14/30/all-time window
- Health score + Keep/Watch/Rest/Replace for lists (wear-out, 3-day trend) and CLIs (spam-flag detection), CLI+list pairings, best time per list
- Best-time heatmap
- AI directives (auto after upload, plus a manual button), Applied/Ignored/Didn't work feedback, before/after outcome check on the next upload, which writes learned memory
- Streaming AI chat grounded in the data; "REMEMBER:" lines save rules to memory automatically
- Editable AI memory (rules / notes / learned) with an on/off switch per item
- Settings: time zone, thresholds, disposition meaning, list costs → cost per sale

## Backlog
- P1: dedupe repeated chat-saved rules; persist AI job status in DB; confirm before deleting memory; style REMEMBER lines as chips; wider heatmap
- P1: deleting an upload shouldn't remove calls that a later upload skipped as duplicates; option to base cost/sale on all data
- Phase 2: Primo API auto-sync, automatic impact reports, scheduled morning briefing email
- Phase 3: real-time alerts, agent-level insights, team roles & multiple workspaces
