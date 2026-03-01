"use client";

import Link from "next/link";
import { StatTable } from "./stat-table";

export function GamePassingTable({
  data,
  linkPlayers,
}: {
  data: Record<string, unknown>[];
  linkPlayers: boolean;
}) {
  return (
    <StatTable
      data={data}
      defaultSort="yds"
      columns={[
        {
          key: "player_name",
          label: "Player",
          align: "left",
          render: linkPlayers
            ? (r) => (
                <Link href={`/players/${r.player_id}`} className="text-text hover:text-gold">
                  {String(r.player_name)}
                </Link>
              )
            : undefined,
        },
        {
          key: "com",
          label: "C/A",
          align: "right",
          render: (r) => `${r.com}/${r.att}`,
        },
        {
          key: "yds",
          label: "Yds",
          align: "right",
          render: (r) => <span className="text-pass">{String(r.yds)}</span>,
        },
        { key: "td", label: "TD", align: "right" },
        { key: "int_thrown", label: "INT", align: "right" },
        {
          key: "rtg",
          label: "Rtg",
          align: "right",
          render: (r) => (r.rtg != null ? Number(r.rtg).toFixed(1) : "-"),
        },
      ]}
    />
  );
}

export function GameRushingTable({
  data,
  linkPlayers,
}: {
  data: Record<string, unknown>[];
  linkPlayers: boolean;
}) {
  return (
    <StatTable
      data={data}
      defaultSort="yds"
      columns={[
        {
          key: "player_name",
          label: "Player",
          align: "left",
          render: linkPlayers
            ? (r) => (
                <Link href={`/players/${r.player_id}`} className="text-text hover:text-gold">
                  {String(r.player_name)}
                </Link>
              )
            : undefined,
        },
        { key: "att", label: "Att", align: "right" },
        {
          key: "yds",
          label: "Yds",
          align: "right",
          render: (r) => <span className="text-rush">{String(r.yds)}</span>,
        },
        {
          key: "avg",
          label: "Avg",
          align: "right",
          render: (r) => (r.avg != null ? Number(r.avg).toFixed(1) : "-"),
        },
        { key: "td", label: "TD", align: "right" },
        { key: "lg", label: "Lg", align: "right" },
      ]}
    />
  );
}

export function GameReceivingTable({
  data,
  linkPlayers,
}: {
  data: Record<string, unknown>[];
  linkPlayers: boolean;
}) {
  return (
    <StatTable
      data={data}
      defaultSort="yds"
      columns={[
        {
          key: "player_name",
          label: "Player",
          align: "left",
          render: linkPlayers
            ? (r) => (
                <Link href={`/players/${r.player_id}`} className="text-text hover:text-gold">
                  {String(r.player_name)}
                </Link>
              )
            : undefined,
        },
        { key: "rec", label: "Rec", align: "right" },
        {
          key: "yds",
          label: "Yds",
          align: "right",
          render: (r) => <span className="text-rec">{String(r.yds)}</span>,
        },
        {
          key: "avg",
          label: "Avg",
          align: "right",
          render: (r) => (r.avg != null ? Number(r.avg).toFixed(1) : "-"),
        },
        { key: "td", label: "TD", align: "right" },
        { key: "lg", label: "Lg", align: "right" },
      ]}
    />
  );
}
