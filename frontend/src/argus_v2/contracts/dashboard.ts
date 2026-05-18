import { z } from "zod";

export const freshnessStatusSchema = z.enum(["fresh", "partial", "stale", "missing"]);
export const directionToneSchema = z.enum(["positive", "neutral", "negative"]);
export const optionPressureSideSchema = z.enum(["CALL", "PUT", "NEUTRAL", "UNKNOWN"]);
export const optionQuotePressureSideSchema = z.enum(["CALL", "PUT", "BALANCED", "UNKNOWN"]);
export const connectionStrengthSchema = z.enum(["strong", "medium", "weak", "unclear"]);
export const judgementLabelSchema = z.enum(["강한 상방", "상방 우위", "중립", "하방 우위", "강한 하방"]);
export const confidenceLevelSchema = z.enum(["low", "medium", "high"]);

const dataPointSchema = z.object({
  value: z.union([z.number(), z.string()]).nullable(),
  unit: z.string(),
  source: z.string(),
  observed_at: z.string().nullable(),
  freshness: freshnessStatusSchema,
});

const providerHealthSchema = z.object({
  key: z.string(),
  label: z.string(),
  status: freshnessStatusSchema,
  state: z.string().nullable().optional(),
  last_success_at: z.string().nullable(),
  next_scheduled_run: z.string().nullable().optional(),
  observed_count: z.number(),
  missing_fields: z.array(z.string()),
  error: z.string().nullable(),
});

const optionKeyLevelSchema = z.object({
  role: z.enum(["atm", "call_wall", "put_wall", "pressure"]),
  label: z.string(),
  side: optionPressureSideSchema,
  strike_price: z.number().nullable(),
  summary: z.string(),
  source: z.string(),
  observed_at: z.string().nullable(),
  freshness: freshnessStatusSchema,
});

const optionOpenInterestChangeSchema = z.object({
  freshness: freshnessStatusSchema,
  call_change_rate: z.number().nullable(),
  put_change_rate: z.number().nullable(),
  net_change_rate: z.number().nullable(),
  total_change_rate: z.number().nullable(),
  dominant_side: optionPressureSideSchema,
  source: z.string(),
  observed_at: z.string().nullable(),
});

const optionQuoteRowSchema = z.object({
  strike_price: z.number(),
  moneyness: z.string(),
  call_last_price: z.number().nullable(),
  call_change_rate: z.number().nullable(),
  call_volume: z.number().nullable(),
  call_trading_value: z.number().nullable(),
  call_open_interest: z.number().nullable(),
  call_open_interest_change: z.number().nullable(),
  call_implied_volatility: z.number().nullable(),
  put_last_price: z.number().nullable(),
  put_change_rate: z.number().nullable(),
  put_volume: z.number().nullable(),
  put_trading_value: z.number().nullable(),
  put_open_interest: z.number().nullable(),
  put_open_interest_change: z.number().nullable(),
  put_implied_volatility: z.number().nullable(),
  total_open_interest: z.number().nullable(),
  net_call_put_oi: z.number().nullable(),
  call_put_oi_ratio: z.number().nullable(),
  pressure_side: optionQuotePressureSideSchema,
});

export const optionQuotesResponseSchema = z.object({
  as_of: z.string().nullable(),
  trade_date: z.string().nullable(),
  source: z.string(),
  status: freshnessStatusSchema,
  observed_count: z.number(),
  underlying_code: z.string().nullable().optional(),
  underlying_name: z.string().nullable().optional(),
  underlying_price: z.number().nullable().optional(),
  expiry_date: z.string().nullable().optional(),
  contract_month: z.string().nullable().optional(),
  atm_strike: z.number().nullable().optional(),
  rows: z.array(optionQuoteRowSchema),
});

export const futuresQuoteResponseSchema = z.object({
  as_of: z.string().nullable(),
  trade_date: z.string().nullable(),
  source: z.string(),
  status: freshnessStatusSchema,
  observed_count: z.number(),
  session_type: z.string().nullable().optional(),
  instrument_code: z.string().nullable().optional(),
  instrument_name: z.string().nullable().optional(),
  price: z.number().nullable().optional(),
  price_change: z.number().nullable().optional(),
  change_rate: z.number().nullable().optional(),
  volume: z.number().nullable().optional(),
  open_interest: z.number().nullable().optional(),
  put_call_ratio: z.number().nullable().optional(),
  implied_volatility: z.number().nullable().optional(),
  bid: z.number().nullable().optional(),
  ask: z.number().nullable().optional(),
  basis: z.number().nullable().optional(),
  market_basis: z.number().nullable().optional(),
  theoretical_price: z.number().nullable().optional(),
  disparity_rate: z.number().nullable().optional(),
  open_interest_change: z.number().nullable().optional(),
  open_interest_change_rate: z.number().nullable().optional(),
});

const derivativesPressureSchema = z.object({
  foreign_futures_net_buy: dataPointSchema,
  institution_futures_net_buy: dataPointSchema,
  individual_futures_net_buy: dataPointSchema,
  basis: dataPointSchema,
  put_call_ratio: dataPointSchema,
  open_interest_change_rate: dataPointSchema,
  kospi200_futures_change_rate: dataPointSchema,
  option_pressure: optionPressureSideSchema,
  option_open_interest_change: optionOpenInterestChangeSchema,
  key_levels: z.array(optionKeyLevelSchema),
  summary: z.string(),
  freshness: freshnessStatusSchema,
});

const triggerEventSchema = z.object({
  id: z.string(),
  title: z.string(),
  summary: z.string(),
  impact: directionToneSchema,
  source: z.string(),
  published_at: z.string().nullable(),
  connection_strength: connectionStrengthSchema,
  ai_reason: z.string().nullable().optional(),
  ai_confidence: confidenceLevelSchema.nullable().optional(),
  affected_factors: z.array(z.string()).optional(),
  freshness: freshnessStatusSchema,
});

const newsFeedItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  summary: z.string(),
  source: z.string(),
  published_at: z.string().nullable(),
  source_url: z.string().nullable().optional(),
  freshness: freshnessStatusSchema,
});

export const newsFeedResponseSchema = z.object({
  as_of: z.string(),
  provider: z.string(),
  status: freshnessStatusSchema,
  observed_count: z.number(),
  error: z.string().nullable().optional(),
  items: z.array(newsFeedItemSchema),
});

const sectorMoveSchema = z.object({
  name: z.string(),
  change_rate: z.number().nullable(),
  reason: z.string(),
  tone: directionToneSchema,
  source: z.string(),
  observed_at: z.string().nullable(),
});

const marketReactionSchema = z.object({
  kospi_change_rate: dataPointSchema,
  kosdaq_change_rate: dataPointSchema,
  kospi200_futures_change_rate: dataPointSchema,
  advancing_count: dataPointSchema,
  declining_count: dataPointSchema,
  spot_foreign_net_buy: dataPointSchema,
  spot_institution_net_buy: dataPointSchema,
  spot_individual_net_buy: dataPointSchema,
  strong_sectors: z.array(sectorMoveSchema),
  weak_sectors: z.array(sectorMoveSchema),
  summary: z.string(),
  freshness: freshnessStatusSchema,
});

const marketJudgementSchema = z.object({
  label: judgementLabelSchema,
  summary: z.string(),
  primary_driver: z.string(),
  confidence: confidenceLevelSchema,
  data_reliability: freshnessStatusSchema,
  reasons: z.array(z.string()),
  counter_evidence: z.array(z.string()),
  transition_condition: z.string(),
  watch_points: z.array(z.string()),
  source: z.literal("rule_based"),
});

export const marketDashboardSchema = z.object({
  as_of: z.string(),
  session_phase: z.enum(["pre_open", "live", "post_close"]),
  derivatives: derivativesPressureSchema,
  triggers: z.array(triggerEventSchema),
  reaction: marketReactionSchema,
  judgement: marketJudgementSchema,
  provider_health: z.array(providerHealthSchema),
});

export type MarketDashboard = z.infer<typeof marketDashboardSchema>;
export type DataPoint = z.infer<typeof dataPointSchema>;
export type NewsFeedResponse = z.infer<typeof newsFeedResponseSchema>;
export type OptionQuotesResponse = z.infer<typeof optionQuotesResponseSchema>;
export type OptionQuoteRow = z.infer<typeof optionQuoteRowSchema>;
export type FuturesQuoteResponse = z.infer<typeof futuresQuoteResponseSchema>;
