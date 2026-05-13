"use client";

import { useState } from "react";
import { fetchPrice, type StockPrice } from "@/app/lib/api";

export default function Home() {
  const [code, setCode] = useState("005930");
  const [data, setData] = useState<StockPrice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await fetchPrice(code.trim());
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-md p-8">
      <h1 className="mb-6 text-2xl font-bold">국내주식 현재가 조회 (모의투자)</h1>
      <form onSubmit={onSubmit} className="mb-6 flex gap-2">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="종목코드 (예: 005930)"
          aria-label="종목코드"
          className="flex-1 rounded border px-3 py-2"
        />
        <button
          type="submit"
          disabled={loading || !code.trim()}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {loading ? "조회 중..." : "조회"}
        </button>
      </form>

      {error && <p className="text-red-600">{error}</p>}

      {data && (
        <div className="rounded-lg border p-4">
          <p className="text-lg font-semibold">
            {data.name} ({data.code})
          </p>
          <p className="text-3xl font-bold">{data.price.toLocaleString()}원</p>
          <p className={data.change >= 0 ? "text-red-600" : "text-blue-600"}>
            {data.change >= 0 ? "▲" : "▼"} {Math.abs(data.change).toLocaleString()} (
            {data.change_rate}%)
          </p>
          <p className="text-sm text-gray-500">
            누적 거래량 {data.volume.toLocaleString()}
          </p>
        </div>
      )}
    </main>
  );
}
