import { z } from "zod";

export const marketFlowDataModeSchema = z.enum(["mock", "live"]);
export const marketFlowStatusSchema = z.enum(["fresh", "partial", "stale", "missing"]);
export const marketFlowFreshnessSchema = z.enum(["fresh", "stale"]);

export const marketFlowFactSchema = z.object({
  source: z.string(),
  source_record_id: z.string(),
  data_mode: marketFlowDataModeSchema,
  is_live: z.boolean(),
  market_scope: z.literal("KRX"),
  quality: z.enum(["estimate", "confirmed"]),
  trade_date: z.string(),
  observed_at: z.string(),
  collected_at: z.string(),
  freshness: marketFlowFreshnessSchema,
  unit: z.literal("KRW"),
  individual_net: z.number(),
  foreign_net: z.number(),
  institution_net: z.number(),
});

export const marketFlowRowSchema = z.object({
  segment: z.enum(["kospi_spot", "kospi200_futures", "kospi200_call", "kospi200_put"]),
  label: z.string(),
  status: marketFlowStatusSchema,
  estimate: marketFlowFactSchema.nullable(),
  confirmed: marketFlowFactSchema.nullable(),
});

export const marketFlowDashboardSchema = z.object({
  as_of: z.string(),
  data_mode: marketFlowDataModeSchema,
  is_live: z.boolean(),
  market_scope: z.literal("KRX"),
  status: marketFlowStatusSchema,
  rows: z.array(marketFlowRowSchema),
});

export type MarketFlowFact = z.infer<typeof marketFlowFactSchema>;
export type MarketFlowRow = z.infer<typeof marketFlowRowSchema>;
export type MarketFlowDashboard = z.infer<typeof marketFlowDashboardSchema>;

