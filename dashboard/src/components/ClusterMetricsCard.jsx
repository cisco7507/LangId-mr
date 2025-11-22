import React from 'react';
import { useClusterMetricsSummary } from '../hooks/useClusterMetricsSummary';

function ClusterMetricsCard() {
    const { data, loading, error, lastUpdated } = useClusterMetricsSummary();

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
                <h3 className="text-sm font-medium text-rose-800">Cluster Metrics Unavailable</h3>
                <p className="text-xs text-rose-600 mt-1">
                    Unable to load cluster health data.
                </p>
            </div>
        );
    }

    const nodes = data?.nodes || [];
    const totalTraffic = nodes.reduce((sum, node) => sum + (node.jobs_submitted_as_target || 0), 0);

    return (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm flex flex-col h-full">
            <div className="border-b border-slate-200 px-4 py-3">
                <div className="flex items-center justify-between">
                    <h3 className="text-sm font-medium text-slate-900">Cluster Health and Load</h3>
                    {lastUpdated && (
                        <span className="text-[10px] text-slate-500">
                            Updated {lastUpdated.toLocaleTimeString()}
                        </span>
                    )}
                </div>
            </div>

            <div className="p-0 overflow-x-auto">
                {nodes.length === 0 ? (
                    <div className="p-4 text-center text-sm text-slate-500">
                        No cluster nodes configured.
                    </div>
                ) : (
                    <table className="w-full text-left text-xs">
                        <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-100">
                            <tr>
                                <th className="px-4 py-2">Node</th>
                                <th className="px-4 py-2">Status</th>
                                <th className="px-4 py-2 text-right">Owned</th>
                                <th className="px-4 py-2 text-right">Active</th>
                                <th className="px-4 py-2 text-right">Traffic</th>
                                <th className="px-4 py-2 text-right">Last Health</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {nodes.map((node) => {
                                const trafficPercent = totalTraffic > 0
                                    ? Math.round(((node.jobs_submitted_as_target || 0) / totalTraffic) * 100)
                                    : 0;

                                return (
                                    <tr key={node.name} className="hover:bg-slate-50">
                                        <td className="px-4 py-2 font-medium text-slate-900">{node.name}</td>
                                        <td className="px-4 py-2">
                                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${node.up
                                                    ? "bg-emerald-100 text-emerald-800"
                                                    : "bg-rose-100 text-rose-800"
                                                }`}>
                                                {node.up ? "UP" : "DOWN"}
                                            </span>
                                        </td>
                                        <td className="px-4 py-2 text-right font-mono">{node.jobs_owned_total}</td>
                                        <td className="px-4 py-2 text-right font-mono">{node.jobs_active}</td>
                                        <td className="px-4 py-2 text-right">
                                            <div className="flex items-center justify-end gap-2">
                                                <span className="text-slate-600">{trafficPercent}%</span>
                                                <div className="w-12 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full bg-blue-500 rounded-full"
                                                        style={{ width: `${trafficPercent}%` }}
                                                    />
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-4 py-2 text-right text-slate-500 whitespace-nowrap">
                                            {node.last_health_ts
                                                ? new Date(node.last_health_ts * 1000).toLocaleTimeString()
                                                : "-"}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}

export default ClusterMetricsCard;
