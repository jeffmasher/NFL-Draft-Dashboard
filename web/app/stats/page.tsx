"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StatTable } from "@/components/stat-table";

type Scope = "career" | "season" | "game";
type Category = "passing" | "rushing" | "receiving" | "defense";
type GameType = "regular" | "playoff" | "preseason";

export default function StatsPage() {
  const [scope, setScope] = useState<Scope>("career");
  const [category, setCategory] = useState<Category>("passing");
  const [gameType, setGameType] = useState<GameType>("regular");
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/leaders?scope=${scope}&category=${category}&gameType=${gameType}`)
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [scope, category, gameType]);

  const columns = buildColumns(scope, category);
  const defaultSort = category === "defense" ? "tkl" : "yds";

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <h1 className="mb-6 font-heading text-3xl font-bold text-gold">
        LEADERBOARDS
      </h1>

      {/* Scope Tabs */}
      <div className="mb-4 flex gap-1 rounded-lg border border-border bg-smoke p-1">
        {(["career", "season", "game"] as Scope[]).map((s) => (
          <button
            key={s}
            onClick={() => setScope(s)}
            className={`flex-1 rounded-md px-3 py-2 font-heading text-sm font-bold uppercase transition-colors ${
              scope === s
                ? "bg-panel text-gold"
                : "text-dim hover:text-text"
            }`}
          >
            {s === "game" ? "Single Game" : s}
          </button>
        ))}
      </div>

      {/* Game Type Tabs */}
      <div className="mb-4 flex gap-2">
        {([["regular", "Regular Season"], ["playoff", "Postseason"], ["preseason", "Preseason"]] as [GameType, string][]).map(([gt, label]) => (
          <button
            key={gt}
            onClick={() => setGameType(gt)}
            className={`rounded-md px-4 py-1.5 font-heading text-xs font-bold uppercase transition-colors ${
              gameType === gt
                ? "bg-gold/20 text-gold"
                : "bg-panel text-dim hover:text-text"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Category Tabs */}
      <div className="mb-6 flex gap-2">
        {(["passing", "rushing", "receiving", "defense"] as Category[]).map((c) => {
          const color =
            c === "passing"
              ? "pass"
              : c === "rushing"
                ? "rush"
                : c === "receiving"
                  ? "rec"
                  : "dim";
          const active = category === c;
          return (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={`rounded-md px-4 py-2 font-heading text-xs font-bold uppercase transition-colors ${
                active
                  ? c === "defense"
                    ? "bg-gold/20 text-gold"
                    : `bg-${color}/20 text-${color}`
                  : "bg-panel text-dim hover:text-text"
              }`}
            >
              {c}
            </button>
          );
        })}
      </div>

      {/* Table */}
      {loading ? (
        <div className="py-12 text-center font-body text-dim">Loading...</div>
      ) : (
        <div className="rounded-lg border border-border">
          <StatTable
            data={data}
            defaultSort={defaultSort}
            columns={columns}
          />
        </div>
      )}
    </div>
  );
}

function buildColumns(scope: Scope, category: Category) {
  const cols: {
    key: string;
    label: string;
    align: "left" | "right" | "center";
    render?: (row: Record<string, unknown>) => React.ReactNode;
  }[] = [];

  cols.push({
    key: "player_name",
    label: "Player",
    align: "left",
    render: (row) => (
      <Link
        href={`/players/${row.player_id}`}
        className="text-text hover:text-gold hover:underline"
      >
        {String(row.player_name)}
      </Link>
    ),
  });

  if (scope === "season") {
    cols.push({
      key: "season",
      label: "Season",
      align: "center",
      render: (row) => (
        <Link href={`/seasons/${row.season}`} className="text-gold hover:underline">
          {String(row.season)}
        </Link>
      ),
    });
  }

  if (scope === "game") {
    cols.push({
      key: "opponent",
      label: "Opp",
      align: "left",
      render: (row) => <span className="text-dim">{String(row.opponent ?? "")}</span>,
    });
    cols.push({
      key: "game_date",
      label: "Date",
      align: "center",
      render: (row) => <span className="text-dim">{String(row.game_date ?? "")}</span>,
    });
  }

  if (category === "passing") {
    const color = "text-pass";
    cols.push({ key: "com", label: "Comp", align: "right" });
    cols.push({ key: "att", label: "Att", align: "right" });
    cols.push({
      key: "yds",
      label: "Yards",
      align: "right",
      render: (row) => (
        <span className={`font-bold ${color}`}>{Number(row.yds).toLocaleString()}</span>
      ),
    });
    cols.push({ key: "td", label: "TD", align: "right" });
    cols.push({ key: "int_thrown", label: "INT", align: "right" });
  }

  if (category === "rushing") {
    const color = "text-rush";
    cols.push({ key: "att", label: "Att", align: "right" });
    cols.push({
      key: "yds",
      label: "Yards",
      align: "right",
      render: (row) => (
        <span className={`font-bold ${color}`}>{Number(row.yds).toLocaleString()}</span>
      ),
    });
    cols.push({ key: "td", label: "TD", align: "right" });
  }

  if (category === "receiving") {
    const color = "text-rec";
    cols.push({ key: "rec", label: "Rec", align: "right" });
    cols.push({
      key: "yds",
      label: "Yards",
      align: "right",
      render: (row) => (
        <span className={`font-bold ${color}`}>{Number(row.yds).toLocaleString()}</span>
      ),
    });
    cols.push({ key: "td", label: "TD", align: "right" });
  }

  if (category === "defense") {
    cols.push({
      key: "tkl",
      label: "Tkl",
      align: "right",
      render: (row) => (
        <span className="font-bold text-gold">{String(row.tkl)}</span>
      ),
    });
    cols.push({ key: "tfl", label: "TFL", align: "right" });
    cols.push({ key: "sacks", label: "Sack", align: "right" });
    cols.push({ key: "int_count", label: "INT", align: "right" });
    cols.push({ key: "ff", label: "FF", align: "right" });
    cols.push({ key: "pd_count", label: "PD", align: "right" });
    cols.push({ key: "qh", label: "QH", align: "right" });
  }

  if (scope !== "game") {
    cols.push({
      key: "games",
      label: "Games",
      align: "right",
      render: (row) => <span className="text-dim">{String(row.games)}</span>,
    });
  }

  return cols;
}
