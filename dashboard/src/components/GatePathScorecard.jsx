import React from 'react';
import { useGatePathMetrics } from '../hooks/useGatePathMetrics';

// Human-readable labels for gate paths
const GATE_PATH_LABELS = {
    high_confidence: 'High Confidence',
    mid_zone_stopword: 'Mid-Zone Stopword',
    vad_retry: 'VAD Retry',
    fallback_scoring: 'Fallback Scoring',
    music_only: 'Music Only',
    unknown: 'Unknown',
};

// Color classes for different gate paths
const GATE_PATH_COLORS = {
    high_confidence: 'bg-emerald-500',
    mid_zone_stopword: 'bg-sky-500',
    vad_retry: 'bg-amber-500',
    fallback_scoring: 'bg-orange-500',
    music_only: 'bg-purple-500',
    unknown: 'bg-slate-400',
};

function GatePathScorecard() {
    const { data, loading, error, lastUpdated } = useGatePathMetrics();

    if (loading && !data) {
        return (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm animate-pulse">
                <div className="h-4 w-1/3 bg-slate-200 rounded mb-4"></div>
                <div className="space-y-2">
                    <div className="h-3 w-full bg-slate-200 rounded"></div>
                    <div className="h-3 w-full bg-slate-200 rounded"></div>
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

    const totalDecisions = data?.total_decisions || 0;
    const byGatePath = data?.by_gate_path || {};
    const percentages = data?.percentages || {};

    // Sort gate paths by count (descending)
    const sortedPaths = Object.entries(byGatePath)
        .filter(([, count]) => count > 0)
        .sort(([, a], [, b]) => b - a);

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
                {totalDecisions === 0 ? (
                    <div className="text-center text-sm text-slate-500 py-4">
                        No gate path decisions recorded yet.
                    </div>
                ) : (
                    <>
                        {/* Total count */}
                        <div className="mb-4 text-center">
                            <span className="text-2xl font-semibold text-slate-900">{totalDecisions}</span>
                            <span className="text-sm text-slate-500 ml-2">total decisions</span>
                        </div>

                        {/* Progress bars for each gate path */}
                        <div className="space-y-3">
                            {sortedPaths.map(([gatePath, count]) => {
                                const percentage = percentages[gatePath] || 0;
                                const label = GATE_PATH_LABELS[gatePath] || gatePath;
                                const colorClass = GATE_PATH_COLORS[gatePath] || 'bg-slate-400';

                                return (
                                    <div key={gatePath}>
                                        <div className="flex items-center justify-between text-xs mb-1">
                                            <span className="font-medium text-slate-700">{label}</span>
                                            <span className="text-slate-500">
                                                {count} ({percentage}%)
                                            </span>
                                        </div>
                                        <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                                            <div
                                                className={`h-full ${colorClass} rounded-full transition-all duration-300`}
                                                style={{ width: `${percentage}%` }}
                                            />
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Legend */}
                        <div className="mt-4 pt-4 border-t border-slate-100">
                            <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-2">Gate Path Legend</p>
                            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px] text-slate-500">
                                <div><span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1"></span>High Confidence: Auto-detected with high probability</div>
                                <div><span className="inline-block w-2 h-2 rounded-full bg-sky-500 mr-1"></span>Mid-Zone: Stopword heuristic confirmed</div>
                                <div><span className="inline-block w-2 h-2 rounded-full bg-amber-500 mr-1"></span>VAD Retry: Required voice activity detection</div>
                                <div><span className="inline-block w-2 h-2 rounded-full bg-orange-500 mr-1"></span>Fallback: EN/FR scoring probe used</div>
                                <div><span className="inline-block w-2 h-2 rounded-full bg-purple-500 mr-1"></span>Music Only: Background music detected</div>
                                <div><span className="inline-block w-2 h-2 rounded-full bg-slate-400 mr-1"></span>Unknown: Unclassified decision</div>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

export default GatePathScorecard;
