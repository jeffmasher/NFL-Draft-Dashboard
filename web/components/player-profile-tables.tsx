"use client";

import Link from "next/link";
import { StatTable } from "./stat-table";

export function SeasonPassingTable({ data }: { data: Record<string, unknown>[] }) {
  return (
    <StatTable
      data={data}
      defaultSort="season"
      defaultAsc={true}
      columns={[
        { key: "season", label: "Season", align: "left" },
        { key: "pass_games", label: "GP", align: "right" },
        { key: "pass_com", label: "Comp", align: "right" },
        { key: "pass_att", label: "Att", align: "right" },
        {
          key: "pass_yds",
          label: "Yards",
          align: "right",
          render: (r) => Number(r.pass_yds).toLocaleString(),
        },
        { key: "pass_td", label: "TD", align: "right" },
        { key: "pass_int", label: "INT", align: "right" },
      ]}
    />
  );
}

export function SeasonRushingTable({ data }: { data: Record<string, unknown>[] }) {
  return (
    <StatTable
      data={data}
      defaultSort="season"
      defaultAsc={true}
      columns={[
        { key: "season", label: "Season", align: "left" },
        { key: "rush_games", label: "GP", align: "right" },
        { key: "rush_att", label: "Att", align: "right" },
        {
          key: "rush_yds",
          label: "Yards",
          align: "right",
          render: (r) => Number(r.rush_yds).toLocaleString(),
        },
        { key: "rush_td", label: "TD", align: "right" },
      ]}
    />
  );
}

export function SeasonReceivingTable({ data }: { data: Record<string, unknown>[] }) {
  return (
    <StatTable
      data={data}
      defaultSort="season"
      defaultAsc={true}
      columns={[
        { key: "season", label: "Season", align: "left" },
        { key: "rec_games", label: "GP", align: "right" },
        { key: "rec", label: "Rec", align: "right" },
        {
          key: "rec_yds",
          label: "Yards",
          align: "right",
          render: (r) => Number(r.rec_yds).toLocaleString(),
        },
        { key: "rec_td", label: "TD", align: "right" },
      ]}
    />
  );
}

export function PlayerGameLogTable({
  data,
  hasPassing,
  hasRushing,
  hasReceiving,
}: {
  data: Record<string, unknown>[];
  hasPassing: boolean;
  hasRushing: boolean;
  hasReceiving: boolean;
}) {
  return (
    <StatTable
      data={data}
      defaultSort="game_date"
      columns={[
        {
          key: "game_date",
          label: "Date",
          align: "left",
          render: (r) => (
            <Link href={`/games/${r.game_id}`} className="text-dim hover:text-gold">
              {String(r.game_date)}
            </Link>
          ),
        },
        {
          key: "opponent",
          label: "Opp",
          align: "left",
          render: (r) => (
            <span>
              {r.home_away === "home" ? "vs " : "@ "}
              {String(r.opponent)}
            </span>
          ),
        },
        {
          key: "result",
          label: "W/L",
          align: "center",
          render: (r) => (
            <span className={r.result === "W" ? "text-rush" : r.result === "L" ? "text-rec" : "text-dim"}>
              {String(r.result)}
            </span>
          ),
        },
        ...(hasPassing
          ? [
              {
                key: "pass_yds",
                label: "PYd",
                align: "right" as const,
                render: (r: Record<string, unknown>) => (
                  <span className="text-pass">{r.pass_yds != null ? String(r.pass_yds) : "-"}</span>
                ),
              },
              { key: "pass_td", label: "PTD", align: "right" as const },
              { key: "pass_int", label: "INT", align: "right" as const },
            ]
          : []),
        ...(hasRushing
          ? [
              {
                key: "rush_yds",
                label: "RYd",
                align: "right" as const,
                render: (r: Record<string, unknown>) => (
                  <span className="text-rush">{r.rush_yds != null ? String(r.rush_yds) : "-"}</span>
                ),
              },
              { key: "rush_td", label: "RTD", align: "right" as const },
            ]
          : []),
        ...(hasReceiving
          ? [
              { key: "rec", label: "Rec", align: "right" as const },
              {
                key: "rec_yds",
                label: "RecYd",
                align: "right" as const,
                render: (r: Record<string, unknown>) => (
                  <span className="text-rec">{r.rec_yds != null ? String(r.rec_yds) : "-"}</span>
                ),
              },
              { key: "rec_td", label: "RecTD", align: "right" as const },
            ]
          : []),
      ]}
    />
  );
}
