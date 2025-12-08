'use client';

import { useState, useMemo, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  TrendingUp,
  TrendingDown,
  Maximize2,
  Minimize2,
  Settings,
  Camera,
  ZoomIn,
  ZoomOut,
  Activity,
  BarChart2,
  Layers,
} from 'lucide-react';
import { cn, formatNumber, formatUSD } from '../lib/utils';

interface ChartData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface ProChartProps {
  symbol: string;
  data: ChartData[];  // Required - no mock data
  height?: number;
  showVolume?: boolean;
  showIndicators?: boolean;
  className?: string;
}

// Calculate moving average
function calculateMA(data: ChartData[], period: number): (number | null)[] {
  return data.map((_, i) => {
    if (i < period - 1) return null;
    const slice = data.slice(i - period + 1, i + 1);
    return slice.reduce((sum, d) => sum + d.close, 0) / period;
  });
}

// Calculate RSI
function calculateRSI(data: ChartData[], period: number = 14): (number | null)[] {
  const rsi: (number | null)[] = [];
  
  for (let i = 0; i < data.length; i++) {
    if (i < period) {
      rsi.push(null);
      continue;
    }
    
    let gains = 0;
    let losses = 0;
    
    for (let j = i - period + 1; j <= i; j++) {
      const change = data[j].close - data[j - 1].close;
      if (change > 0) gains += change;
      else losses -= change;
    }
    
    const avgGain = gains / period;
    const avgLoss = losses / period;
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi.push(100 - (100 / (1 + rs)));
  }
  
  return rsi;
}

export default function ProChart({
  symbol,
  data: propData,
  height = 400,
  showVolume = true,
  showIndicators = true,
  className,
}: ProChartProps) {
  const [chartType, setChartType] = useState<'candle' | 'line' | 'area'>('candle');
  const [timeframe, setTimeframe] = useState<'1H' | '4H' | '1D' | '1W'>('1D');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showMA, setShowMA] = useState(true);
  const [crosshair, setCrosshair] = useState<{ x: number; y: number; data: ChartData | null } | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);

  const data = useMemo(() => propData || [], [propData]);
  const ma20 = useMemo(() => calculateMA(data, 20), [data]);
  const ma50 = useMemo(() => calculateMA(data, 50), [data]);
  const rsi = useMemo(() => calculateRSI(data), [data]);

  // Calculate chart dimensions
  const chartHeight = isFullscreen ? window.innerHeight - 200 : height;
  const volumeHeight = showVolume ? 60 : 0;
  const rsiHeight = showIndicators ? 60 : 0;
  const mainChartHeight = chartHeight - volumeHeight - rsiHeight - 40;

  // Price range
  const prices = data.flatMap(d => [d.high, d.low]);
  const minPrice = Math.min(...prices) * 0.995;
  const maxPrice = Math.max(...prices) * 1.005;
  const priceRange = maxPrice - minPrice;

  // Volume range
  const maxVolume = Math.max(...data.map(d => d.volume));

  // Current price info
  const lastCandle = data[data.length - 1];
  const prevCandle = data[data.length - 2];
  const priceChange = lastCandle.close - prevCandle.close;
  const priceChangePercent = (priceChange / prevCandle.close) * 100;
  const isPositive = priceChange >= 0;

  const getY = (price: number) => {
    return mainChartHeight - ((price - minPrice) / priceRange) * mainChartHeight;
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!chartRef.current) return;
    const rect = chartRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const candleWidth = (rect.width - 60) / data.length;
    const index = Math.floor((x - 60) / candleWidth);
    
    if (index >= 0 && index < data.length) {
      setCrosshair({ x, y, data: data[index] });
    }
  };

  const timeframes = ['1H', '4H', '1D', '1W'] as const;
  const chartTypes = [
    { id: 'candle', icon: BarChart2 },
    { id: 'line', icon: Activity },
    { id: 'area', icon: Layers },
  ] as const;

  return (
    <div className={cn(
      "glass-card rounded-xl overflow-hidden",
      isFullscreen && "fixed inset-4 z-50",
      className
    )}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/5">
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-lg">{symbol}/USD</h3>
              <span className={cn(
                "flex items-center gap-1 text-sm font-medium",
                isPositive ? "text-emerald-400" : "text-red-400"
              )}>
                {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                {isPositive ? '+' : ''}{priceChangePercent.toFixed(2)}%
              </span>
            </div>
            <div className="flex items-center gap-3 mt-1 text-sm">
              <span className="text-2xl font-bold">${formatNumber(lastCandle.close)}</span>
              <span className="text-slate-400">
                H: ${formatNumber(lastCandle.high)} L: ${formatNumber(lastCandle.low)}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Timeframes */}
          <div className="flex items-center gap-1 p-1 rounded-lg bg-surface-2/50">
            {timeframes.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={cn(
                  "px-2.5 py-1 rounded text-xs font-medium transition-colors",
                  timeframe === tf 
                    ? "bg-brand-sky/20 text-brand-sky" 
                    : "text-slate-400 hover:text-white"
                )}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Chart Types */}
          <div className="flex items-center gap-1 p-1 rounded-lg bg-surface-2/50">
            {chartTypes.map(({ id, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setChartType(id as typeof chartType)}
                className={cn(
                  "p-1.5 rounded transition-colors",
                  chartType === id 
                    ? "bg-brand-sky/20 text-brand-sky" 
                    : "text-slate-400 hover:text-white"
                )}
              >
                <Icon className="w-4 h-4" />
              </button>
            ))}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1">
            <button 
              onClick={() => setShowMA(!showMA)}
              className={cn(
                "p-2 rounded-lg transition-colors",
                showMA ? "bg-amber-500/20 text-amber-400" : "text-slate-400 hover:text-white"
              )}
              title="Moving Averages"
            >
              <Activity className="w-4 h-4" />
            </button>
            <button 
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="p-2 rounded-lg text-slate-400 hover:text-white transition-colors"
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div 
        ref={chartRef}
        className="relative"
        style={{ height: chartHeight }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setCrosshair(null)}
      >
        {/* Main Chart */}
        <svg 
          width="100%" 
          height={mainChartHeight} 
          className="overflow-visible"
        >
          {/* Grid */}
          {Array.from({ length: 5 }).map((_, i) => {
            const y = (mainChartHeight / 5) * i;
            const price = maxPrice - (priceRange / 5) * i;
            return (
              <g key={i}>
                <line
                  x1="60"
                  y1={y}
                  x2="100%"
                  y2={y}
                  stroke="rgba(255,255,255,0.05)"
                  strokeDasharray="4,4"
                />
                <text
                  x="55"
                  y={y + 4}
                  textAnchor="end"
                  className="text-[10px] fill-slate-500"
                >
                  ${formatNumber(price)}
                </text>
              </g>
            );
          })}

          {/* Moving Averages */}
          {showMA && (
            <>
              {/* MA20 */}
              <polyline
                fill="none"
                stroke="#f59e0b"
                strokeWidth="1.5"
                opacity="0.8"
                points={data.map((d, i) => {
                  const ma = ma20[i];
                  if (ma === null) return '';
                  const x = 60 + (i / (data.length - 1)) * (100 - 60);
                  return `${x}%,${getY(ma)}`;
                }).filter(Boolean).join(' ')}
              />
              {/* MA50 */}
              <polyline
                fill="none"
                stroke="#8b5cf6"
                strokeWidth="1.5"
                opacity="0.8"
                points={data.map((d, i) => {
                  const ma = ma50[i];
                  if (ma === null) return '';
                  const x = 60 + (i / (data.length - 1)) * (100 - 60);
                  return `${x}%,${getY(ma)}`;
                }).filter(Boolean).join(' ')}
              />
            </>
          )}

          {/* Candlesticks or Line */}
          {chartType === 'candle' ? (
            data.map((d, i) => {
              const isUp = d.close >= d.open;
              const x = 60 + (i / (data.length - 1)) * 100 + '%';
              const candleWidth = Math.max(2, 100 / data.length - 1);
              
              return (
                <g key={i}>
                  {/* Wick */}
                  <line
                    x1={x}
                    y1={getY(d.high)}
                    x2={x}
                    y2={getY(d.low)}
                    stroke={isUp ? '#10b981' : '#ef4444'}
                    strokeWidth="1"
                  />
                  {/* Body */}
                  <rect
                    x={`calc(${x} - ${candleWidth / 2}px)`}
                    y={getY(Math.max(d.open, d.close))}
                    width={candleWidth}
                    height={Math.max(1, Math.abs(getY(d.open) - getY(d.close)))}
                    fill={isUp ? '#10b981' : '#ef4444'}
                    rx="1"
                  />
                </g>
              );
            })
          ) : chartType === 'line' ? (
            <polyline
              fill="none"
              stroke="#06b6d4"
              strokeWidth="2"
              points={data.map((d, i) => {
                const x = 60 + (i / (data.length - 1)) * (100 - 60);
                return `${x}%,${getY(d.close)}`;
              }).join(' ')}
            />
          ) : (
            <>
              <defs>
                <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#06b6d4" stopOpacity="0" />
                </linearGradient>
              </defs>
              <polygon
                fill="url(#areaGradient)"
                points={`60,${mainChartHeight} ${data.map((d, i) => {
                  const x = 60 + (i / (data.length - 1)) * (100 - 60);
                  return `${x}%,${getY(d.close)}`;
                }).join(' ')} 100%,${mainChartHeight}`}
              />
              <polyline
                fill="none"
                stroke="#06b6d4"
                strokeWidth="2"
                points={data.map((d, i) => {
                  const x = 60 + (i / (data.length - 1)) * (100 - 60);
                  return `${x}%,${getY(d.close)}`;
                }).join(' ')}
              />
            </>
          )}
        </svg>

        {/* Volume */}
        {showVolume && (
          <div className="border-t border-white/5" style={{ height: volumeHeight }}>
            <svg width="100%" height={volumeHeight}>
              {data.map((d, i) => {
                const x = 60 + (i / (data.length - 1)) * 100 + '%';
                const barWidth = Math.max(2, 100 / data.length - 1);
                const barHeight = (d.volume / maxVolume) * (volumeHeight - 10);
                const isUp = d.close >= d.open;

                return (
                  <rect
                    key={i}
                    x={`calc(${x} - ${barWidth / 2}px)`}
                    y={volumeHeight - barHeight - 5}
                    width={barWidth}
                    height={barHeight}
                    fill={isUp ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}
                    rx="1"
                  />
                );
              })}
            </svg>
          </div>
        )}

        {/* RSI */}
        {showIndicators && (
          <div className="border-t border-white/5 p-2" style={{ height: rsiHeight }}>
            <div className="text-[10px] text-slate-500 mb-1">RSI(14)</div>
            <svg width="100%" height={rsiHeight - 20}>
              {/* Overbought/Oversold lines */}
              <line x1="0" y1="30%" x2="100%" y2="30%" stroke="rgba(239, 68, 68, 0.3)" strokeDasharray="2,2" />
              <line x1="0" y1="70%" x2="100%" y2="70%" stroke="rgba(16, 185, 129, 0.3)" strokeDasharray="2,2" />
              
              <polyline
                fill="none"
                stroke="#8b5cf6"
                strokeWidth="1.5"
                points={rsi.map((r, i) => {
                  if (r === null) return '';
                  const x = (i / (data.length - 1)) * 100;
                  const y = 100 - r;
                  return `${x}%,${y}%`;
                }).filter(Boolean).join(' ')}
              />
            </svg>
          </div>
        )}

        {/* Crosshair */}
        {crosshair && crosshair.data && (
          <>
            <div 
              className="absolute top-0 bottom-0 w-px bg-slate-500/50 pointer-events-none"
              style={{ left: crosshair.x }}
            />
            <div 
              className="absolute left-0 right-0 h-px bg-slate-500/50 pointer-events-none"
              style={{ top: crosshair.y }}
            />
            <div 
              className="absolute bg-surface-1 border border-white/10 rounded-lg p-2 text-xs pointer-events-none shadow-lg"
              style={{ 
                left: crosshair.x + 10, 
                top: crosshair.y + 10,
                transform: crosshair.x > 300 ? 'translateX(-120%)' : 'none'
              }}
            >
              <div className="font-medium mb-1">
                {new Date(crosshair.data.time).toLocaleDateString()}
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-slate-400">
                <span>O:</span><span className="text-white">${formatNumber(crosshair.data.open)}</span>
                <span>H:</span><span className="text-emerald-400">${formatNumber(crosshair.data.high)}</span>
                <span>L:</span><span className="text-red-400">${formatNumber(crosshair.data.low)}</span>
                <span>C:</span><span className="text-white">${formatNumber(crosshair.data.close)}</span>
                <span>Vol:</span><span className="text-slate-300">{formatUSD(crosshair.data.volume)}</span>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Legend */}
      {showMA && (
        <div className="flex items-center gap-4 px-4 py-2 border-t border-white/5 text-xs text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-amber-500 rounded" />
            MA(20)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-purple-500 rounded" />
            MA(50)
          </span>
        </div>
      )}
    </div>
  );
}
