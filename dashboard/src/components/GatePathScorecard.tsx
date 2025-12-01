import React, { useMemo } from "react";
import { useGatePathMetrics } from "../hooks/useGatePathMetrics";
import {
  GATE_PATH_META,
  normalizeGatePathKey,
  GatePathKey,
  GatePathMeta,
} from "../gatePaths";

const CANONICAL_KEYS = Object.keys(GATE_PATH_META) as GatePathKey[];

type PathSummary = {
  key: GatePathKey;
  meta: GatePathMeta;
  count: number;
  percentage: number;
};

const formatPercentage = (value: number): string => {
  if (!Number.isFinite(value) || value <= 0) {
    return "0%";
  }
  const rounded = Number(value.toFixed(1));
  return `${Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)}%`;
};

const GatePathScorecard: React.FC = () => {
  const { data, loading, error, lastUpdated } = useGatePathMetrics();

  const totalDecisions = data?.total_decisions ?? 0;
  const rawByGatePath = data?.by_gate_path;

  const normalizedCounts = useMemo(() => {
    const baseCounts = {} as Record<GatePathKey, number>;
    CANONICAL_KEYS.forEach((key) => {
      baseCounts[key] = 0;
    });

    Object.entries(rawByGatePath ?? {}).forEach(([rawKey, count]) => {
      const normalizedKey = normalizeGatePathKey(rawKey);
      const numericCount = typeof count === "number" ? count : Number(count) || 0;
      baseCounts[normalizedKey] = (baseCounts[normalizedKey] ?? 0) + numericCount;
    });

    return baseCounts;
  }, [rawByGatePath]);

  const pathSummaries = useMemo<PathSummary[]>(() => {
    return CANONICAL_KEYS.map((key) => {
      const meta = GATE_PATH_META[key];
      const count = normalizedCounts[key] ?? 0;
      const percentage = totalDecisions > 0 ? (count / totalDecisions) * 100 : 0;
      return { key, meta, count, percentage };
    });
  }, [normalizedCounts, totalDecisions]);

  const activeSummaries = useMemo(() => {
    return pathSummaries
      .filter((summary) => summary.count > 0)
      .sort((a, b) => b.count - a.count);
  }, [pathSummaries]);

  const displaySummaries = activeSummaries.length > 0 ? activeSummaries : pathSummaries;
  const hasData = totalDecisions > 0;

  if (loading && !data) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm animate-pulse">
        <div className="h-4 w-1/3 bg-slate-200 rounded mb-4" />
        <div className="space-y-2">
          <div className="h-3 w-full bg-slate-200 rounded" />
          <div className="h-3 w-full bg-slate-200 rounded" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 shadow-sm">
        <h3 className="text-sm font-medium text-rose-800">Gate Path Metrics Unavailable</h3>
        <p className="text-xs text-rose-600 mt-1">
          Unable to load gate path decision data.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm flex flex-col h-full">
      <div className="border-b border-slate-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-slate-900">Gate Path Decisions</h3>
          {lastUpdated && (
            <span className="text-[10px] text-slate-500">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Distribution of language detection decisions by gate path
        </p>
      </div>

      <div className="p-4">
        {!hasData ? (
          <div className="text-center text-sm text-slate-500 py-4">
            No gate path decisions recorded yet.
          </div>
        ) : (
          <>
            <div className="mb-4 text-center">
              <span className="text-2xl font-semibold text-slate-900">{totalDecisions}</span>
              <span className="text-sm text-slate-500 ml-2">total decisions</span>
            </div>

            <div className="space-y-3">
              {displaySummaries.map(({ key, meta, count, percentage }) => (
                <div key={key}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-medium text-slate-700">{meta.label}</span>
                    <span className="text-slate-500">
                      {count} ({formatPercentage(percentage)})
                    </span>
                  </div>
                  <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${Math.min(percentage, 100)}%`,
                        backgroundColor: meta.color,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100">
              <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-3">
                Gate Path Legend
              </p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                {pathSummaries.map(({ key, meta, count }) => {
                  const isInactive = count === 0;
                  return (
                    <div key={key} className="flex gap-2">
                      <span
                        className="mt-1 inline-block h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: meta.color }}
                        aria-hidden="true"
                      />
                      <div>
                        <p
                          className={`text-[11px] font-medium ${
                            isInactive ? "text-slate-400" : "text-slate-600"
                          }`}
                        >
                          {meta.label}
                        </p>
                        <p className="text-[10px] text-slate-400 leading-tight">
                          {meta.description}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default GatePathScorecard;
