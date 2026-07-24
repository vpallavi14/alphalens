// PredictionBadge.tsx
// Displays the XGBoost classifier output (UP / DOWN / NEUTRAL) with a
// confidence percentage, styled to the AlphaLens dark theme.

import React from "react";

export type Prediction = "UP" | "DOWN" | "NEUTRAL";

export interface PredictionBadgeProps {
  /** XGBoost classifier signal */
  prediction: Prediction;
  /** Model confidence score in the range 0–1 */
  confidence: number;
}

const BADGE_STYLES: Record<Prediction, { label: string; icon: string; classes: string }> = {
  UP: {
    label: "UP",
    icon: "▲",
    classes: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  },
  DOWN: {
    label: "DOWN",
    icon: "▼",
    classes: "text-red-400 bg-red-400/10 border-red-400/20",
  },
  NEUTRAL: {
    label: "NEUTRAL",
    icon: "—",
    classes: "text-slate-400 bg-slate-700/50 border-slate-600/30",
  },
};

export default function PredictionBadge({ prediction, confidence }: PredictionBadgeProps) {
  const { label, icon, classes } = BADGE_STYLES[prediction];
  const confidencePct = Math.round(Math.min(Math.max(confidence, 0), 1) * 100);

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-semibold tracking-wide ${classes}`}
    >
      <span aria-hidden="true">{icon}</span>
      <span>{label}</span>
      <span className="opacity-75">{confidencePct}%</span>
    </span>
  );
}
