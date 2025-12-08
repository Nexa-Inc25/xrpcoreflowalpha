'use client';

import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { 
  Activity, 
  AlertTriangle, 
  CheckCircle, 
  Database, 
  Cpu, 
  Wifi, 
  TrendingUp,
  Clock,
  BarChart3,
  RefreshCw,
  XCircle,
  Info
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://api.zkalphaflow.com';

interface PipelineHealth {
  timestamp: string;
  overall_status: 'healthy' | 'degraded' | 'unhealthy';
  issues: string[];
  signal_ingestion: {
    total_signals: number;
    signals_last_hour: number;
    signals_last_24h: number;
    by_type: Record<string, { count: number; avg_confidence: number }>;
    latest_signal_seconds_ago: number | null;
    ingestion_rate_per_hour: number;
  };
  scanners: Record<string, { connected: boolean; error?: string }>;
  ml_training: {
    xgboost: {
      is_fitted: boolean;
      training_samples: number;
      training_rmse?: number;
      training_runs?: number;
    };
    flow_predictor: {
      is_fitted: boolean;
    };
  };
  outcome_tracking: {
    total_outcomes: number;
    overall_hit_rate: number;
    by_interval: Record<string, { count: number; hits: number; hit_rate: number }>;
    tracking_active: boolean;
  };
  database: {
    connected: boolean;
    table_count: number;
    size_mb: number;
  };
  connections: Record<string, { status: string }>;
}

interface MLMetrics {
  timestamp: string;
  xgboost: {
    model_version: string;
    is_fitted: boolean;
    training_rmse: number;
    feature_names: string[];
    xgboost_available: boolean;
  };
  training_data: {
    latency_events: number;
    training_runs: number;
    high_confidence_signals: number;
    ready_for_training: boolean;
    samples_needed: number;
  };
  recommendations: string[];
}

interface SystemAlerts {
  timestamp: string;
  alert_count: number;
  alerts: Array<{
    level: 'info' | 'warning' | 'error';
    component: string;
    message: string;
    action: string;
  }>;
}

async function fetchPipelineHealth(): Promise<PipelineHealth> {
  const res = await fetch(`${API_BASE}/admin/pipeline-health`);
  if (!res.ok) throw new Error('Failed to fetch pipeline health');
  return res.json();
}

async function fetchMLMetrics(): Promise<MLMetrics> {
  const res = await fetch(`${API_BASE}/admin/ml-metrics`);
  if (!res.ok) throw new Error('Failed to fetch ML metrics');
  return res.json();
}

async function fetchAlerts(): Promise<SystemAlerts> {
  const res = await fetch(`${API_BASE}/admin/alerts`);
  if (!res.ok) throw new Error('Failed to fetch alerts');
  return res.json();
}

function StatusBadge({ status }: { status: 'healthy' | 'degraded' | 'unhealthy' | string }) {
  const config = {
    healthy: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', icon: CheckCircle },
    degraded: { bg: 'bg-amber-500/20', text: 'text-amber-400', icon: AlertTriangle },
    unhealthy: { bg: 'bg-rose-500/20', text: 'text-rose-400', icon: XCircle },
  };
  const c = config[status as keyof typeof config] || config.degraded;
  const Icon = c.icon;
  
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${c.bg} ${c.text}`}>
      <Icon className="w-3.5 h-3.5" />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function ConnectionStatus({ connected }: { connected: boolean }) {
  return connected ? (
    <span className="flex items-center gap-1.5 text-emerald-400 text-sm">
      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
      Connected
    </span>
  ) : (
    <span className="flex items-center gap-1.5 text-rose-400 text-sm">
      <span className="w-2 h-2 rounded-full bg-rose-400" />
      Disconnected
    </span>
  );
}

export default function AdminMonitoringPage() {
  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useQuery({
    queryKey: ['pipeline-health'],
    queryFn: fetchPipelineHealth,
    refetchInterval: 30000, // Refresh every 30s
  });

  const { data: mlMetrics, isLoading: mlLoading } = useQuery({
    queryKey: ['ml-metrics'],
    queryFn: fetchMLMetrics,
    refetchInterval: 60000, // Refresh every 60s
  });

  const { data: alerts } = useQuery({
    queryKey: ['system-alerts'],
    queryFn: fetchAlerts,
    refetchInterval: 30000,
  });

  if (healthLoading || mlLoading) {
    return (
      <div className="min-h-screen bg-surface-1 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-brand-cyan border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface-1 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Pipeline Monitoring</h1>
            <p className="text-slate-400 text-sm mt-1">
              Real-time visibility into data ingestion and ML training
            </p>
          </div>
          <div className="flex items-center gap-4">
            <StatusBadge status={health?.overall_status || 'degraded'} />
            <button 
              onClick={() => refetchHealth()}
              className="p-2 rounded-lg bg-surface-2 hover:bg-surface-3 transition-colors"
            >
              <RefreshCw className="w-4 h-4 text-slate-400" />
            </button>
          </div>
        </div>

        {/* Issues Banner */}
        {health?.issues && health.issues.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4"
          >
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 mt-0.5" />
              <div>
                <h3 className="font-medium text-amber-400">Active Issues</h3>
                <ul className="mt-2 space-y-1">
                  {health.issues.map((issue, i) => (
                    <li key={i} className="text-sm text-slate-300">• {issue}</li>
                  ))}
                </ul>
              </div>
            </div>
          </motion.div>
        )}

        {/* Main Grid */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Signal Ingestion */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-5 rounded-xl"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold flex items-center gap-2">
                <Activity className="w-4 h-4 text-brand-cyan" />
                Signal Ingestion
              </h2>
              <span className="text-xs text-slate-500">
                {health?.signal_ingestion?.latest_signal_seconds_ago 
                  ? `${Math.round(health.signal_ingestion.latest_signal_seconds_ago / 60)}m ago`
                  : 'No data'}
              </span>
            </div>
            
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="bg-surface-2 rounded-lg p-3">
                <p className="text-xs text-slate-500">Last Hour</p>
                <p className="text-xl font-bold text-white">
                  {health?.signal_ingestion?.signals_last_hour || 0}
                </p>
              </div>
              <div className="bg-surface-2 rounded-lg p-3">
                <p className="text-xs text-slate-500">Last 24h</p>
                <p className="text-xl font-bold text-white">
                  {health?.signal_ingestion?.signals_last_24h || 0}
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-xs text-slate-500 font-medium">By Type</p>
              {health?.signal_ingestion?.by_type && Object.entries(health.signal_ingestion.by_type).map(([type, data]) => (
                <div key={type} className="flex items-center justify-between text-sm">
                  <span className="text-slate-300 capitalize">{type}</span>
                  <span className="text-white font-mono">
                    {data.count} <span className="text-slate-500">({data.avg_confidence}%)</span>
                  </span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* ML Training Status */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-5 rounded-xl"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold flex items-center gap-2">
                <Cpu className="w-4 h-4 text-brand-purple" />
                ML Training
              </h2>
              {health?.ml_training?.xgboost?.is_fitted ? (
                <span className="text-xs text-emerald-400">Trained</span>
              ) : (
                <span className="text-xs text-amber-400">Not Trained</span>
              )}
            </div>

            <div className="space-y-4">
              {/* XGBoost */}
              <div className="bg-surface-2 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">XGBoost</span>
                  <ConnectionStatus connected={health?.ml_training?.xgboost?.is_fitted || false} />
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <p className="text-slate-500">Training Samples</p>
                    <p className="text-white font-mono">{mlMetrics?.training_data?.latency_events || 0}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Samples Needed</p>
                    <p className="text-white font-mono">{mlMetrics?.training_data?.samples_needed || 500}</p>
                  </div>
                </div>
                {/* Progress bar */}
                <div className="mt-2">
                  <div className="h-1.5 bg-surface-3 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-brand-cyan rounded-full transition-all duration-500"
                      style={{ 
                        width: `${Math.min(100, ((mlMetrics?.training_data?.latency_events || 0) / 500) * 100)}%` 
                      }}
                    />
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    {Math.round(((mlMetrics?.training_data?.latency_events || 0) / 500) * 100)}% to auto-training
                  </p>
                </div>
              </div>

              {/* Recommendations */}
              {mlMetrics?.recommendations && mlMetrics.recommendations.length > 0 && (
                <div className="text-xs space-y-1">
                  <p className="text-slate-500 font-medium">Recommendations</p>
                  {mlMetrics.recommendations.map((rec, i) => (
                    <p key={i} className="text-slate-400">• {rec}</p>
                  ))}
                </div>
              )}
            </div>
          </motion.div>

          {/* System Connections */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-5 rounded-xl"
          >
            <h2 className="font-semibold flex items-center gap-2 mb-4">
              <Wifi className="w-4 h-4 text-brand-sky" />
              Connections
            </h2>

            <div className="space-y-3">
              {/* Database */}
              <div className="flex items-center justify-between p-3 bg-surface-2 rounded-lg">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-slate-400" />
                  <span className="text-sm">Database</span>
                </div>
                <div className="text-right">
                  <ConnectionStatus connected={health?.database?.connected || false} />
                  <p className="text-xs text-slate-500">{health?.database?.size_mb || 0} MB</p>
                </div>
              </div>

              {/* Scanners */}
              {health?.scanners && Object.entries(health.scanners).map(([name, status]) => (
                <div key={name} className="flex items-center justify-between p-3 bg-surface-2 rounded-lg">
                  <span className="text-sm capitalize">{name.replace('_', ' ')}</span>
                  <ConnectionStatus connected={status.connected} />
                </div>
              ))}

              {/* External APIs */}
              {health?.connections && Object.entries(health.connections).map(([name, status]) => (
                <div key={name} className="flex items-center justify-between p-3 bg-surface-2 rounded-lg">
                  <span className="text-sm capitalize">{name.replace('_', ' ')}</span>
                  <ConnectionStatus connected={status.status === 'connected'} />
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Outcome Tracking */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass-card p-5 rounded-xl"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-emerald-400" />
              Outcome Tracking & Validation
            </h2>
            {health?.outcome_tracking?.tracking_active ? (
              <span className="text-xs text-emerald-400">Active</span>
            ) : (
              <span className="text-xs text-amber-400">Collecting...</span>
            )}
          </div>

          <div className="grid md:grid-cols-4 gap-4">
            <div className="bg-surface-2 rounded-lg p-4">
              <p className="text-xs text-slate-500">Total Outcomes</p>
              <p className="text-2xl font-bold text-white">
                {health?.outcome_tracking?.total_outcomes || 0}
              </p>
            </div>
            <div className="bg-surface-2 rounded-lg p-4">
              <p className="text-xs text-slate-500">Overall Hit Rate</p>
              <p className="text-2xl font-bold text-emerald-400">
                {health?.outcome_tracking?.overall_hit_rate || 0}%
              </p>
            </div>
            {health?.outcome_tracking?.by_interval && Object.entries(health.outcome_tracking.by_interval).map(([interval, data]) => (
              <div key={interval} className="bg-surface-2 rounded-lg p-4">
                <p className="text-xs text-slate-500">{interval} Hit Rate</p>
                <p className="text-2xl font-bold text-white">
                  {data.hit_rate}%
                  <span className="text-xs text-slate-500 ml-1">({data.count})</span>
                </p>
              </div>
            ))}
          </div>
        </motion.div>

        {/* System Alerts */}
        {alerts && alerts.alerts.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="glass-card p-5 rounded-xl"
          >
            <h2 className="font-semibold flex items-center gap-2 mb-4">
              <Info className="w-4 h-4 text-blue-400" />
              System Alerts ({alerts.alert_count})
            </h2>

            <div className="space-y-3">
              {alerts.alerts.map((alert, i) => (
                <div 
                  key={i}
                  className={`p-4 rounded-lg ${
                    alert.level === 'warning' ? 'bg-amber-500/10 border border-amber-500/30' :
                    alert.level === 'error' ? 'bg-rose-500/10 border border-rose-500/30' :
                    'bg-blue-500/10 border border-blue-500/30'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <p className={`font-medium ${
                        alert.level === 'warning' ? 'text-amber-400' :
                        alert.level === 'error' ? 'text-rose-400' :
                        'text-blue-400'
                      }`}>
                        {alert.component.replace('_', ' ')}
                      </p>
                      <p className="text-sm text-slate-300 mt-1">{alert.message}</p>
                      <p className="text-xs text-slate-500 mt-2">
                        Action: {alert.action}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Footer */}
        <div className="text-center text-xs text-slate-500 pt-4">
          Last updated: {health?.timestamp ? new Date(health.timestamp).toLocaleString() : 'Unknown'}
          <span className="mx-2">•</span>
          Auto-refresh: 30s
        </div>
      </div>
    </div>
  );
}
