export function money(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

export function num(n: number): string {
  return n.toLocaleString();
}

export function pct(n: number): string {
  return `${n.toFixed(0)}%`;
}
