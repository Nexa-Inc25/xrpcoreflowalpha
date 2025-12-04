'use client';

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';

type PricePoint = {
  t: number;
  p: number;
};

interface PriceChartProps {
  data: PricePoint[];
  assetSymbol: string;
  eventTime?: number | null;
}

function formatTime(value: number): string {
  const d = new Date(value);
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

export default function PriceChart({ data, assetSymbol, eventTime }: PriceChartProps) {
  if (!data || data.length === 0) {
    return <div className="text-xs text-slate-400">No price data available.</div>;
  }

  const prices = data.map((p) => p.p);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const domain = [min * 0.995, max * 1.005];

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="priceArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.9} />
              <stop offset="100%" stopColor="#0f172a" stopOpacity={0.1} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
          <XAxis
            dataKey="t"
            tickFormatter={formatTime}
            tick={{ fontSize: 10, fill: '#9ca3af' }}
          />
          <YAxis
            domain={domain}
            tick={{ fontSize: 10, fill: '#9ca3af' }}
            tickFormatter={(v: number) => v.toFixed(2)}
          />
          <Tooltip
            contentStyle={{ backgroundColor: '#020617', borderColor: '#1f2937' }}
            labelFormatter={(v: number) => formatTime(v)}
            formatter={(value: any) => [`$${Number(value).toFixed(4)}`, `${assetSymbol}/USD`]}
          />
          <Area
            type="monotone"
            dataKey="p"
            stroke="#38bdf8"
            strokeWidth={2}
            fill="url(#priceArea)"
          />
          {eventTime && (
            <ReferenceLine x={eventTime} stroke="#f97316" strokeDasharray="3 3" />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
