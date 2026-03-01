"use client";

import Link from "next/link";
import { StatTable } from "./stat-table";

export function SeasonGameTable({ data }: { data: Record<string, unknown>[] }) {
  return (
    <StatTable
      data={data}
      defaultSort="game_date"
      defaultAsc={true}
      title="game-log"
      columns={[
        {
          key: "game_date",
          label: "Date",
          align: "left",
          render: (r) => <span className="text-dim">{String(r.game_date)}</span>,
        },
        {
          key: "home_away",
          label: "",
          align: "center",
          render: (r) => (
            <span className="text-dim">{r.home_away === "home" ? "vs" : "@"}</span>
          ),
        },
        {
          key: "opponent",
          label: "Opponent",
          align: "left",
          render: (r) => (
            <Link
              href={`/games/${r.game_id}`}
              className="text-text hover:text-gold hover:underline"
            >
              {String(r.opponent)}
            </Link>
          ),
        },
        {
          key: "saints_score",
          label: "Score",
          align: "right",
          render: (r) => (
            <span className="text-text">
              {String(r.saints_score)}&ndash;{String(r.opponent_score)}
            </span>
          ),
        },
        {
          key: "result",
          label: "W/L",
          align: "center",
          render: (r) => (
            <span
              className={
                r.result === "W"
                  ? "text-rush"
                  : r.result === "L"
                    ? "text-rec"
                    : "text-dim"
              }
            >
              {String(r.result)}
            </span>
          ),
        },
      ]}
    />
  );
}
