import { z } from "zod";

const envSchema = z.object({
  BACKEND_BASE_URL: z.string().url().default("http://localhost:4000"),
});

export const argusV2Env = envSchema.parse({
  BACKEND_BASE_URL: process.env.BACKEND_BASE_URL,
});

