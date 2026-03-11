import { z } from "zod";

const envSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  BACKEND_BASE_URL: z.string().url().default("http://localhost:4000"),
});

export const env = envSchema.parse({
  NODE_ENV: process.env.NODE_ENV,
  BACKEND_BASE_URL: process.env.BACKEND_BASE_URL,
});
