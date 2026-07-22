import { z } from "zod";

const envSchema = z.object({
  BACKEND_BASE_URL: z.string().url().default("http://localhost:4000"),
});

export const marketTerminalEnv = envSchema.parse({
  BACKEND_BASE_URL: process.env.BACKEND_BASE_URL,
});

