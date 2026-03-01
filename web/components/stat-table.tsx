"use client";

import { useState, useRef, useCallback } from "react";

interface Column<T> {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  render?: (row: T) => React.ReactNode;
  sortable?: boolean;
}

interface StatTableProps<T> {
  data: T[];
  columns: Column<T>[];
  defaultSort?: string;
  defaultAsc?: boolean;
  title?: string;
}

export function StatTable<T extends Record<string, unknown>>({
  data,
  columns,
  defaultSort,
  defaultAsc = false,
  title,
}: StatTableProps<T>) {
  const [sortCol, setSortCol] = useState(defaultSort ?? columns[0]?.key);
  const [sortAsc, setSortAsc] = useState(defaultAsc);
  const tableRef = useRef<HTMLTableElement>(null);

  const sorted = [...data].sort((a, b) => {
    const av = a[sortCol];
    const bv = b[sortCol];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === "string" && typeof bv === "string") {
      return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    }
    return sortAsc
      ? (av as number) - (bv as number)
      : (bv as number) - (av as number);
  });

  const handleSort = (key: string) => {
    if (sortCol === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortCol(key);
      setSortAsc(false);
    }
  };

  // Build totals row — sum numeric columns, skip averages/ratings
  const skipKeys = new Set(["avg", "rtg", "pct", "lg", "season", "game_date", "result", "home_away", "game_id", "player_id"]);
  const totals: Record<string, unknown> = {};
  let firstCol = true;
  for (const col of columns) {
    if (firstCol && col.align !== "right" && col.align !== "center") {
      totals[col.key] = "Total";
      firstCol = false;
      continue;
    }
    firstCol = false;
    if (skipKeys.has(col.key)) {
      totals[col.key] = null;
      continue;
    }
    const nums = data.map((r) => r[col.key]).filter((v) => v != null && typeof v === "number") as number[];
    if (nums.length > 0 && nums.length === data.filter((r) => r[col.key] != null).length) {
      const sum = nums.reduce((a, b) => a + b, 0);
      totals[col.key] = Number.isInteger(sum) ? sum : Math.round(sum * 10) / 10;
    } else {
      totals[col.key] = null;
    }
  }
  const showTotals = data.length > 1;

  const exportCSV = useCallback(() => {
    const header = columns.map((c) => c.label).join(",");
    const rows = sorted.map((row) =>
      columns
        .map((col) => {
          const val = row[col.key];
          const str = val == null ? "" : String(val);
          return str.includes(",") || str.includes('"')
            ? `"${str.replace(/"/g, '""')}"`
            : str;
        })
        .join(",")
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title || "table"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [columns, sorted, title]);

  const exportJPEG = useCallback(async () => {
    if (!tableRef.current) return;
    const { toJpeg } = await import("html-to-image");
    const dataUrl = await toJpeg(tableRef.current, {
      backgroundColor: "#1a1a1a",
      quality: 0.95,
      pixelRatio: 2,
    });
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = `${title || "table"}.jpg`;
    a.click();
  }, [title]);

  return (
    <div className="overflow-x-auto">
      <div className="flex justify-end gap-2 mb-1">
        <button
          onClick={exportCSV}
          className="text-xs text-dim hover:text-gold transition-colors cursor-pointer"
          title="Download CSV"
        >
          CSV
        </button>
        <button
          onClick={exportJPEG}
          className="text-xs text-dim hover:text-gold transition-colors cursor-pointer"
          title="Download JPEG"
        >
          JPEG
        </button>
      </div>
      <table ref={tableRef} className="w-full font-mono text-sm">
        <thead>
          <tr className="border-b border-border text-dim">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-3 py-2 font-medium ${
                  col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"
                } ${col.sortable !== false ? "cursor-pointer select-none hover:text-gold" : ""}`}
                onClick={() => col.sortable !== false && handleSort(col.key)}
              >
                {col.label}
                {sortCol === col.key && (
                  <span className="ml-1 text-gold">{sortAsc ? "\u25B2" : "\u25BC"}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr
              key={i}
              className="border-b border-border/50 transition-colors hover:bg-panel"
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`px-3 py-2 ${
                    col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"
                  }`}
                >
                  {col.render ? col.render(row) : String(row[col.key] ?? "-")}
                </td>
              ))}
            </tr>
          ))}
          {showTotals && (
            <tr className="border-t-2 border-gold/40 font-bold text-gold">
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`px-3 py-2 ${
                    col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"
                  }`}
                >
                  {totals[col.key] != null ? String(totals[col.key]) : ""}
                </td>
              ))}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
