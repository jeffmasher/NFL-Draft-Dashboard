"use client";

import Link from "next/link";
import { StatTable } from "./stat-table";

export function PlayersStatsTable({ data }: { data: Record<string, unknown>[] }) {
  return (
    <StatTable
      data={data}
      defaultSort="pass_yds"
      columns={[
        {
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
        },
        {
          key: "position",
          label: "Pos",
          align: "left",
          render: (row) =>
            row.position ? (
              <span className="text-gold">{String(row.position)}</span>
            ) : (
              <span className="text-dim">-</span>
            ),
        },
        {
          key: "pass_yds",
          label: "Pass Yds",
          align: "right",
          render: (row) =>
            Number(row.pass_yds) > 0 ? (
              <span className="text-pass">{Number(row.pass_yds).toLocaleString()}</span>
            ) : (
              <span className="text-dim">-</span>
            ),
        },
        {
          key: "pass_td",
          label: "Pass TD",
          align: "right",
          render: (row) => (Number(row.pass_td) > 0 ? String(row.pass_td) : "-"),
        },
        {
          key: "rush_yds",
          label: "Rush Yds",
          align: "right",
          render: (row) =>
            Number(row.rush_yds) > 0 ? (
              <span className="text-rush">{Number(row.rush_yds).toLocaleString()}</span>
            ) : (
              <span className="text-dim">-</span>
            ),
        },
        {
          key: "rush_td",
          label: "Rush TD",
          align: "right",
          render: (row) => (Number(row.rush_td) > 0 ? String(row.rush_td) : "-"),
        },
        {
          key: "rec_yds",
          label: "Rec Yds",
          align: "right",
          render: (row) =>
            Number(row.rec_yds) > 0 ? (
              <span className="text-rec">{Number(row.rec_yds).toLocaleString()}</span>
            ) : (
              <span className="text-dim">-</span>
            ),
        },
        {
          key: "rec_td",
          label: "Rec TD",
          align: "right",
          render: (row) => (Number(row.rec_td) > 0 ? String(row.rec_td) : "-"),
        },
      ]}
    />
  );
}

export function PlayersSearchTable({ data }: { data: Record<string, unknown>[] }) {
  return (
    <StatTable
      data={data}
      defaultSort="player_name"
      defaultAsc={true}
      columns={[
        {
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
        },
        {
          key: "position",
          label: "Pos",
          align: "left",
          render: (row) =>
            row.position ? (
              <span className="text-gold">{String(row.position)}</span>
            ) : (
              <span className="text-dim">-</span>
            ),
        },
        { key: "first_season", label: "First", align: "right" },
        { key: "last_season", label: "Last", align: "right" },
      ]}
    />
  );
}
