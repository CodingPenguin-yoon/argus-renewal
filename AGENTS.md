# AGENTS.md

## Argus defaults
- Product: Korean-market situation cockpit for beginner-to-intermediate retail investors, optimized for before-open and intraday market reads.
- Stack: Next.js App Router, TypeScript, Tailwind CSS, Prisma, SQLite for local development, Zod, pnpm.
- UX: desktop-first MVP, research-desk clarity with control-room speed, clear information hierarchy, loading/empty/error states, accessible semantic HTML, keyboard-friendly interactions, financial disclaimer, Korean market color convention with up red and down blue.
- Architecture: keep code simple and maintainable, preserve provider/adapter foundations for news, derivatives, and macro sources, run without external API keys, include mock and seed data, separate domain types/providers/utilities/UI components.
- Product shape: derivatives/options positioning is the core layer, real news/macro triggers contextualize or challenge it, market reaction confirms or weakens it.
- Surface defaults: main tabs are dashboard, derivatives/options, market reaction, and news/triggers; AI is an interpretation layer inside screens, not a separate tab.
- MVP scope: watchlist is out of MVP unless the task explicitly changes product scope.
- Delivery: implement code instead of stopping at planning, run relevant lint/test/build checks, update `README.md` and `.env.example` when behavior or configuration changes.

## Argus operating mode
- The main Codex session is the coordinator.
- Model preference: use GPT-5.5 with xhigh reasoning for the main session whenever the client/API configuration allows it.
- Multi-agent preference: when the user explicitly authorizes subagents and the tool allows model override, spawn subagents with `model=gpt-5.5` and `reasoning_effort=xhigh`.
- If a platform-provided subagent role has a tool-enforced fixed model that cannot be overridden, state that limitation before relying on that role; prefer a GPT-5.5 xhigh default subagent or keep the work local when that better matches the user's model policy.
- For non-trivial tasks, delegate in order: explorer, reviewer, docs_researcher, then worker.
- Only worker is allowed to edit code.
- Do not start worker until explorer and reviewer have returned.
- Prefer concise summaries over raw logs and long command dumps.
- Keep the main thread focused on requirements, decisions, and final output.

## When to skip multi-agent
- Single-file trivial edits
- Known typo fixes
- Mechanical updates with already-known file targets

## Delegation order
1. explorer scopes code paths, impacted files, symbols, configs, migrations, and likely tests
2. reviewer checks correctness, regressions, security, and missing coverage
3. docs_researcher verifies framework, API, and config assumptions
4. worker makes the smallest coherent change

## Definition of done
- Scope is clear
- Change is minimal and targeted
- Relevant validation ran
- Remaining risk is explicitly stated

## Avoid
- Broad scans when targeted reads are enough
- Speculative refactors
- Style-only review comments
- Silent changes to behavior or contracts
