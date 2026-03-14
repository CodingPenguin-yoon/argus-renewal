import { env } from "@/krx/lib/env";
import { GlobalEventItem, GlobalEventsCoverage } from "@/krx/types/domain";

const BACKEND_BASE_URL = env.BACKEND_BASE_URL.replace(/\/+$/, "");

type ApiGlobalEventRelease = {
  metric_code: string | null;
  state: string;
  unit: string | null;
  previous: string | null;
  forecast: string | null;
  actual: string | null;
  surprise: string | null;
  previous_value: number | null;
  forecast_value: number | null;
  actual_value: number | null;
  surprise_value: number | null;
  source_name: string | null;
  source_url: string | null;
  source_record_id: string | null;
  actual_released_at: string | null;
};

type ApiGlobalEventImpact = {
  summary_ko: string;
  tone: "risk_on" | "risk_off" | "hawkish" | "dovish" | "neutral" | "mixed";
  impact_channels: string[];
  generation_method: "rule_based" | "llm";
  provider_name: string | null;
  model_name: string | null;
};

type ApiGlobalEventItem = {
  id: string;
  event_key: string;
  title: string;
  event_type: string;
  category: string;
  country: string;
  status: string;
  importance: "high" | "medium" | "low" | null;
  importance_source: string | null;
  event_date_kst: string;
  event_time_kst: string | null;
  event_time_precision: "time" | "date";
  previous_event_time_kst: string | null;
  revision_note: string | null;
  why_it_matters_ko: string;
  source: {
    key: string;
    name: string;
    url: string | null;
    updated_at: string | null;
  };
  release: ApiGlobalEventRelease;
  impact: ApiGlobalEventImpact | null;
  provenance: Record<string, unknown>;
  updated_at: string | null;
};

type ApiGlobalEventsCoverageItem = {
  source_key: string;
  source_name: string;
  source_kind: "schedule" | "release" | "vendor";
  is_required: boolean;
  status: "available" | "partial" | "missing";
  available_count: number;
  expected_count: number;
  coverage_ratio: number;
  event_types: string[];
  last_synced_at: string | null;
  last_success_at: string | null;
  source_url: string | null;
  note: string | null;
  metadata: Record<string, unknown>;
};

type ApiGlobalEventsCoverage = {
  state: "full" | "partial" | "empty";
  coverage_ratio: number;
  available_sources: number;
  expected_sources: number;
  summary: string;
  updated_at: string | null;
  items: ApiGlobalEventsCoverageItem[];
};

type ApiGlobalEventsList = {
  updated_at: string | null;
  items: ApiGlobalEventItem[];
};

async function getGlobalEventsJson<T>(path: string, revalidate = 30): Promise<T> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/global-events${path}`, {
    next: { revalidate },
  });

  if (!response.ok) {
    throw new Error(`Global-events request failed: ${path} (${response.status})`);
  }

  return response.json() as Promise<T>;
}

function mapEvent(item: ApiGlobalEventItem): GlobalEventItem {
  return {
    id: item.id,
    eventKey: item.event_key,
    title: item.title,
    eventType: item.event_type,
    category: item.category,
    country: item.country,
    status: item.status,
    importance: item.importance,
    importanceSource: item.importance_source,
    eventDateKst: item.event_date_kst,
    eventTimeKst: item.event_time_kst,
    eventTimePrecision: item.event_time_precision,
    previousEventTimeKst: item.previous_event_time_kst,
    revisionNote: item.revision_note,
    whyItMattersKo: item.why_it_matters_ko,
    source: {
      key: item.source.key,
      name: item.source.name,
      url: item.source.url,
      updatedAt: item.source.updated_at,
    },
    release: {
      metricCode: item.release.metric_code,
      state: item.release.state,
      unit: item.release.unit,
      previous: item.release.previous,
      forecast: item.release.forecast,
      actual: item.release.actual,
      surprise: item.release.surprise,
      previousValue: item.release.previous_value,
      forecastValue: item.release.forecast_value,
      actualValue: item.release.actual_value,
      surpriseValue: item.release.surprise_value,
      sourceName: item.release.source_name,
      sourceUrl: item.release.source_url,
      sourceRecordId: item.release.source_record_id,
      actualReleasedAt: item.release.actual_released_at,
    },
    impact: item.impact
      ? {
          summaryKo: item.impact.summary_ko,
          tone: item.impact.tone,
          impactChannels: item.impact.impact_channels,
          generationMethod: item.impact.generation_method,
          providerName: item.impact.provider_name,
          modelName: item.impact.model_name,
        }
      : null,
    provenance: item.provenance,
    updatedAt: item.updated_at,
  };
}

function emptyCoverage(): GlobalEventsCoverage {
  return {
    state: "empty",
    coverageRatio: 0,
    availableSources: 0,
    expectedSources: 0,
    summary: "글로벌 이벤트 동기화 이력이 아직 없습니다.",
    updatedAt: null,
    items: [],
  };
}

export async function getGlobalEventsDashboardData() {
  try {
    const [highlight, upcoming, week, coverage] = await Promise.all([
      getGlobalEventsJson<ApiGlobalEventsList>("/highlight"),
      getGlobalEventsJson<ApiGlobalEventsList>("/upcoming?window=24h"),
      getGlobalEventsJson<ApiGlobalEventsList>("/week"),
      getGlobalEventsJson<ApiGlobalEventsCoverage>("/coverage"),
    ]);

    return {
      highlights: highlight.items.map(mapEvent),
      upcoming: upcoming.items.map(mapEvent),
      week: week.items.map(mapEvent),
      coverage: {
        state: coverage.state,
        coverageRatio: coverage.coverage_ratio,
        availableSources: coverage.available_sources,
        expectedSources: coverage.expected_sources,
        summary: coverage.summary,
        updatedAt: coverage.updated_at,
        items: coverage.items.map((item) => ({
          sourceKey: item.source_key,
          sourceName: item.source_name,
          sourceKind: item.source_kind,
          isRequired: item.is_required,
          status: item.status,
          availableCount: item.available_count,
          expectedCount: item.expected_count,
          coverageRatio: item.coverage_ratio,
          eventTypes: item.event_types,
          lastSyncedAt: item.last_synced_at,
          lastSuccessAt: item.last_success_at,
          sourceUrl: item.source_url,
          note: item.note,
          metadata: item.metadata,
        })),
      },
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (!message.includes("Dynamic server usage")) {
      console.error(
        JSON.stringify(
          {
            scope: "krx_global_events_fetch",
            status: "failed",
            error: message,
          },
          null,
          0,
        ),
      );
    }

    return {
      highlights: [] as GlobalEventItem[],
      upcoming: [] as GlobalEventItem[],
      week: [] as GlobalEventItem[],
      coverage: emptyCoverage(),
    };
  }
}
