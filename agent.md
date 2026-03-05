# Project Instructions

## Product Goal
Build a user-friendly financial news web app for beginner-to-intermediate retail investors.

The product should focus on:
1. Macro news (rates, inflation, war/geopolitics, FX, oil, regulation, economy)
2. Stock-specific news (earnings, guidance, M&A, launches, executives, regulation)

The key differentiator is not volume of news, but clarity:
- why the news matters
- which sectors/stocks are affected
- what the user should pay attention to

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
- Mobile-first responsive design
- Clear information hierarchy
- Make content understandable for non-expert investors
- Include loading, empty, and error states
- Add a financial information disclaimer

## Architecture Rules
- Keep code simple and maintainable
- Use provider/adapter patterns for news sources
- App must run without external API keys
- Provide mock data and seed data
- Separate domain types, providers, utilities, and UI components

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
- Avoid unnecessary abstractio
