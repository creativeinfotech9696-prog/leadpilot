# Dialer Intelligence — AI Operations Assistant for Primo Dialer

An AI-powered command center that reads your Primo Dialer reports and tells you which lead lists and CLIs to run, pause, or replace — and when.
It learns from every upload and from how your recommendations played out, so its advice sharpens over time.

## Who it's for
- The owner / operations manager of a US calling business running outbound and inbound campaigns on Primo Dialer.
- Floor managers who need a quick read on what to dial next, without digging through raw reports.

## Core features and experience
- **Report upload (CSV/Excel):** drag in Primo exports (call logs / dispositions). The app maps columns automatically (lead list, CLI, phone, timestamp, direction, disposition, talk time, agent) and asks you to confirm the mapping the first time a new format appears.
- **Performance dashboard:** for each lead list and each CLI — dials, connect rate, contact rate, talk time, completed sales, conversion rate, cost signals (dials per sale). Trends by day and by hour (US time zones), outbound vs inbound split.
- **Lead list health:** each list gets a health score and a status — *Keep running*, *Watch*, *Rest*, *Replace*. Shows when a list is getting exhausted (falling connect rate, repeat dials, rising no-answers).
- **CLI health:** spots CLIs whose answer rate is dropping (likely flagged as spam), recommends rotating or resting them, and which CLIs work best with which lists.
- **Best time to dial:** per list, the hours and weekdays with the highest connect and sale rates.
- **AI recommendations feed:** daily action list ("Pause List X — connect rate down 40% in 3 days", "Move CLI Y to List Z between 10am–1pm EST"), each with the reason and supporting numbers. You mark each as *Applied*, *Ignored*, or *Didn't work*.
- **AI chat assistant:** ask anything in plain English ("Which list should I load tomorrow morning?", "Why did sales drop Tuesday?") and get answers grounded in your actual data, with charts/tables where useful.
- **Adaptive learning:** the assistant keeps a memory of your business — what counts as a sale (only completed sales), which past recommendations worked, your notes and rules ("never dial List A after 6pm"). It checks results after a recommendation was applied and adjusts how it weighs signals next time. You can view and edit this memory.
- **Settings:** choose which disposition names count as a completed sale, connected, or contacted; set your time zone and thresholds.

## User flow
1. Sign in with email and password.
2. Upload the latest Primo export → confirm column and disposition mapping (first time only).
3. Dashboard refreshes with list and CLI performance; AI generates the day's recommendations.
4. Review recommendations, mark what you applied, and ask follow-up questions in the chat.
5. Next upload: the AI compares before/after on applied actions, records what worked, and improves future advice.

## UI/UX feel
A dark, focused "operations control room" look: dense but readable data tables, clear status colors (green / amber / red) for list and CLI health, charts for trends, and the AI chat always one click away as a side panel. Built for desktop first, usable on phone for quick checks.

## Implementation phases
**Phase 1 — MVP (built now)**
- Email/password sign-in.
- CSV/Excel upload with column + disposition mapping; upload history.
- Dashboard: lead list and CLI metrics, hourly/daily trends, outbound vs inbound.
- Health scores and statuses for lists and CLIs.
- AI recommendations feed with Applied / Ignored / Didn't work feedback.
- AI chat assistant grounded in uploaded data (Claude Sonnet 5.5).
- Editable AI memory (business rules, notes, learned outcomes) used in every answer.

**Phase 2**
- Direct Primo Dialer API connection for automatic syncing (replacing manual uploads), once API access and credentials are provided.
- Automatic before/after impact reports on applied recommendations.
- Scheduled daily briefing (e.g., morning summary by email).

**Phase 3**
- Real-time alerts (CLI spam-flag drop, list exhaustion) during the dialing day.
- Agent-level performance insights and list-to-agent matching.
- Team members with roles and multiple campaigns/workspaces.

## Assumptions
- Data comes in as Primo CSV/Excel exports for now; Primo API connection comes in Phase 2 once credentials are available.
- AI model: Claude Sonnet 5.5, using the Emergent universal key (usage is deducted from your Emergent balance).
- Conversion = completed sale only; you select which disposition names mean "completed sale" in settings.
- Sign-in uses Emergent-managed email + password. One shared workspace; the first account created is the owner. Team roles come in Phase 3.
- Lead "packages" are identified by the list/campaign name column in Primo exports.
- Reports and times are shown in US Eastern time by default, changeable in settings.
- "Adaptive" means the AI learns from your feedback, results of applied recommendations, and your saved rules — it does not change dialer settings itself; you stay in control of every action.
- Cost per lead/list is not tracked in Phase 1 unless included in uploads; you can enter list costs manually to see cost per sale.
