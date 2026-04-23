/* ============================================================
   ChartPreview — 迷你图表预览（react-chartjs-2）
   支持: bar / column / line / area / pie / scatter
   ============================================================ */

import React from 'react';
import { Bar, Line, Pie, Scatter } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Filler,
} from 'chart.js';
import type { ChartSuggestion } from '../../types';

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Title, Tooltip, Filler,
);

const PALETTE = ['#003D6E', '#C9A84C', '#48A9E6', '#2ECC71', '#E74C3C', '#9B59B6', '#F39C12'];

interface Props {
  chart: ChartSuggestion;
  width: number;
  height: number;
}

const ChartPreview: React.FC<Props> = ({ chart, width, height }) => {
  // series may arrive as array or single object — normalise to array
  const rawSeries: any[] = Array.isArray(chart.series)
    ? chart.series
    : chart.series
    ? [chart.series]
    : [];

  const labels: string[] = Array.isArray(chart.categories) && chart.categories.length
    ? chart.categories
    : (rawSeries[0]?.labels ?? []);

  const datasets = rawSeries.map((s: any, i: number) => {
    const raw_values = s.values ?? s.data ?? [];
    const values: number[] = Array.isArray(raw_values)
      ? raw_values.map((v: any) => (typeof v === 'number' ? v : parseFloat(v) || 0))
      : [];
    const color = PALETTE[i % PALETTE.length];
    return { label: s.name ?? '', data: values, rawColor: color };
  });

  const type = chart.chart_type ?? 'bar';

  // ── Compact axis options ──
  const axisFont = { size: 7 } as const;
  const compactScales = {
    x: {
      ticks: { font: axisFont, maxRotation: 30, autoSkip: true, maxTicksLimit: 8 },
      grid: { display: false },
    },
    y: {
      ticks: { font: axisFont, maxTicksLimit: 4 },
      grid: { color: '#f0f0f0' as string },
    },
  };
  const noAnimation = { duration: 0 };
  const noTooltip = { enabled: false };
  const compactLegend = {
    display: datasets.length > 1,
    labels: { font: axisFont, padding: 4, boxWidth: 8 },
  };

  // ── Pie / Donut ──
  if (type === 'pie' || type === 'donut') {
    return (
      <Pie
        width={width}
        height={height}
        data={{
          labels,
          datasets: [{
            data: datasets[0]?.data ?? [],
            backgroundColor: PALETTE.slice(0, labels.length).map(c => c + 'CC'),
            borderWidth: 1,
            borderColor: '#fff',
          }],
        }}
        options={{
          responsive: false,
          animation: noAnimation,
          plugins: {
            tooltip: noTooltip,
            legend: {
              display: true,
              position: 'right',
              labels: { font: axisFont, padding: 4, boxWidth: 8 },
            },
          },
        }}
      />
    );
  }

  // ── Scatter ──
  if (type === 'scatter') {
    const scatterData = datasets.map((ds) => ({
      label: ds.label,
      data: ds.data.map((y, i) => ({ x: i, y })),
      backgroundColor: ds.rawColor + 'AA',
      pointRadius: 3,
    }));
    return (
      <Scatter
        width={width}
        height={height}
        data={{ datasets: scatterData }}
        options={{
          responsive: false,
          animation: noAnimation,
          plugins: { tooltip: noTooltip, legend: compactLegend },
          scales: compactScales,
        }}
      />
    );
  }

  // ── Line / Area ──
  if (type === 'line' || type === 'area') {
    const isArea = type === 'area';
    return (
      <Line
        width={width}
        height={height}
        data={{
          labels,
          datasets: datasets.map((ds) => ({
            label: ds.label,
            data: ds.data,
            borderColor: ds.rawColor,
            backgroundColor: ds.rawColor + (isArea ? '44' : '00'),
            borderWidth: 1.5,
            pointRadius: 2,
            tension: 0.3,
            fill: isArea,
          })),
        }}
        options={{
          responsive: false,
          animation: noAnimation,
          plugins: { tooltip: noTooltip, legend: compactLegend },
          scales: compactScales,
        }}
      />
    );
  }

  // ── Bar (horizontal) ──
  if (type === 'bar') {
    return (
      <Bar
        width={width}
        height={height}
        data={{
          labels,
          datasets: datasets.map((ds) => ({
            label: ds.label,
            data: ds.data,
            backgroundColor: ds.rawColor + 'CC',
            borderColor: ds.rawColor,
            borderWidth: 1,
          })),
        }}
        options={{
          indexAxis: 'y',
          responsive: false,
          animation: noAnimation,
          plugins: { tooltip: noTooltip, legend: compactLegend },
          scales: compactScales,
        }}
      />
    );
  }

  // ── Column (vertical bar) — default ──
  return (
    <Bar
      width={width}
      height={height}
      data={{
        labels,
        datasets: datasets.map((ds) => ({
          label: ds.label,
          data: ds.data,
          backgroundColor: ds.rawColor + 'CC',
          borderColor: ds.rawColor,
          borderWidth: 1,
        })),
      }}
      options={{
        responsive: false,
        animation: noAnimation,
        plugins: { tooltip: noTooltip, legend: compactLegend },
        scales: compactScales,
      }}
    />
  );
};

export default ChartPreview;
