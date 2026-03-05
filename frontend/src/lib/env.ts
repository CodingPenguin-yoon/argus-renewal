import { z } from "zod";

const envSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  DATABASE_URL: z.string().default("file:./prisma/dev.db"),
  NEWS_PROVIDER: z.enum(["mock"]).default("mock"),
});

export const env = envSchema.parse({
  NODE_ENV: process.env.NODE_ENV,
  DATABASE_URL: process.env.DATABASE_URL,
  NEWS_PROVIDER: process.env.NEWS_PROVIDER,
});
