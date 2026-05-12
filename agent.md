# Project Instructions

## Product Goal
Build a Korean-market situation cockpit for beginner-to-intermediate retail investors.

The product should help users quickly understand Korean market conditions:
1. Before market open
2. During repeated intraday checks

The core interpretation order is:
1. Derivatives and options positioning first
2. Real news and macro triggers to contextualize or challenge it
3. Market reaction to confirm or weaken the conclusion

The key differentiator is not information volume, but clarity:
- the current market conclusion
- why that conclusion exists
- what evidence conflicts with it
- what the user should watch next

## Tech Preferences
- Next.js App Router
- TypeScript
- Tailwind CSS
- Prisma
- SQLite for local development
- Zod for validation
- pnpm preferred

## UX Rules
- Korean UI by default
- Desktop-first MVP, mobile later
- Clear information hierarchy
- Make content understandable for non-expert investors
- Include loading, empty, and error states
- Add a financial information disclaimer
- Use Korean market color convention: up red, down blue
- Keep the first screen compact: market conclusion, derivatives/options pressure, market reaction, today’s triggers
- Do not create a separate AI Insights tab; AI should be embedded as an interpretation layer
- Do not expand watchlist into MVP by default

## Architecture Rules
- Keep code simple and maintainable
- Use provider/adapter patterns for news, derivatives, and macro sources
- App must run without external API keys
- Provide mock data and seed data
- Separate domain types, providers, utilities, and UI components
- Preserve provider foundations even when product IA changes

## Implementation Rules
- Do not stop at planning
- Actually create, edit, and validate code
- Run lint, test, and build before finishing
- Update README and `.env.example`

## Quality Rules
- TypeScript strict mode
- Accessible semantic HTML
- Keyboard-friendly interactions
- Reusable components
- Avoid unnecessary abstraction
