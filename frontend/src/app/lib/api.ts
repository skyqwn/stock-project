const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface StockPrice {
  code: string;
  name: string;
  price: number;
  change: number;
  change_rate: number;
  volume: number;
}

export async function fetchPrice(code: string): Promise<StockPrice> {
  const res = await fetch(`${API_BASE}/api/stocks/${code}/price`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `요청 실패 (${res.status})`);
  }
  return (await res.json()) as StockPrice;
}
