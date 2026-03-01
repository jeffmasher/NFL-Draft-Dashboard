export const dynamic = "force-dynamic";

import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getSeasonGames,
  getSeasonTeamStats,
  getSeasonPassingLeaders,
  getSeasonRushingLeaders,
  getSeasonReceivingLeaders,
} from "@/lib/queries";
import { SeasonGameTable } from "@/components/season-tables";

export async function generateMetadata({ params }: { params: Promise<{ year: string }> }) {
  const { year } = await params;
  return { title: `${year} Season | Saints Encyclopedia` };
}

export default async function SeasonDetailPage({
  params,
}: {
  params: Promise<{ year: string }>;
}) {
  const { year: yearStr } = await params;
  const year = parseInt(yearStr, 10);
  if (isNaN(year)) notFound();

  const [rawGames, teamStatsArr, passLeaders, rushLeaders, recLeaders] =
    await Promise.all([
      getSeasonGames(year),
      getSeasonTeamStats(year),
      getSeasonPassingLeaders(year),
      getSeasonRushingLeaders(year),
      getSeasonReceivingLeaders(year),
    ]);

  if (rawGames.length === 0) notFound();

  const games = JSON.parse(JSON.stringify(rawGames));
  const teamStats = teamStatsArr[0];
  const regularGames = games.filter((g: Record<string, unknown>) => g.game_type === "regular");
  const playoffGames = games.filter((g: Record<string, unknown>) => g.game_type === "playoff");
  const preseasonGames = games.filter((g: Record<string, unknown>) => g.game_type === "preseason");
  const wins = regularGames.filter((g: Record<string, unknown>) => g.result === "W").length;
  const losses = regularGames.filter((g: Record<string, unknown>) => g.result === "L").length;
  const ties = regularGames.filter((g: Record<string, unknown>) => g.result === "T").length;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      {/* Header */}
      <div className="mb-8 flex items-baseline gap-4">
        <h1 className="font-heading text-4xl font-bold text-gold">{year}</h1>
        <span className="font-mono text-xl text-text">
          {wins}-{losses}
          {ties > 0 ? `-${ties}` : ""}
        </span>
      </div>

      {/* Team Stats */}
      {teamStats && (
        <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          <MiniStat label="Points" value={teamStats.total_points} />
          <MiniStat label="Pass Yds" value={teamStats.pass_yds} color="pass" />
          <MiniStat label="Pass TD" value={teamStats.pass_td} color="pass" />
          <MiniStat label="Rush Yds" value={teamStats.rush_yds} color="rush" />
          <MiniStat label="Rush TD" value={teamStats.rush_td} color="rush" />
          <MiniStat label="INT Thrown" value={teamStats.pass_int} />
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-3">
        {/* Game Results */}
        <div className="lg:col-span-2">
          <h2 className="mb-3 font-heading text-lg font-bold text-text">
            REGULAR SEASON ({regularGames.length} games)
          </h2>
          <div className="mb-6 rounded-lg border border-border">
            <SeasonGameTable data={regularGames} />
          </div>

          {playoffGames.length > 0 && (
            <>
              <h2 className="mb-3 font-heading text-lg font-bold text-text">
                PLAYOFFS
              </h2>
              <div className="mb-6 rounded-lg border border-border">
                <SeasonGameTable data={playoffGames} />
              </div>
            </>
          )}

          {preseasonGames.length > 0 && (
            <>
              <h2 className="mb-3 font-heading text-lg font-bold text-text">
                PRESEASON
              </h2>
              <div className="rounded-lg border border-border">
                <SeasonGameTable data={preseasonGames} />
              </div>
            </>
          )}
        </div>

        {/* Season Leaders */}
        <div>
          <h2 className="mb-3 font-heading text-lg font-bold text-text">
            SEASON LEADERS
          </h2>

          <LeaderSection title="Passing Yards" color="pass" leaders={passLeaders} statKey="yds" />
          <LeaderSection title="Rushing Yards" color="rush" leaders={rushLeaders} statKey="yds" />
          <LeaderSection title="Receiving Yards" color="rec" leaders={recLeaders} statKey="yds" />
        </div>
      </div>
    </div>
  );
}

function MiniStat({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color?: string;
}) {
  const textColor =
    color === "pass"
      ? "text-pass"
      : color === "rush"
        ? "text-rush"
        : color === "rec"
          ? "text-rec"
          : "text-text";
  return (
    <div className="rounded-lg border border-border bg-smoke p-3">
      <div className="font-heading text-[10px] uppercase tracking-wider text-dim">
        {label}
      </div>
      <div className={`mt-0.5 font-mono text-lg font-bold ${textColor}`}>
        {value?.toLocaleString() ?? "-"}
      </div>
    </div>
  );
}

function LeaderSection({
  title,
  color,
  leaders,
  statKey,
}: {
  title: string;
  color: string;
  leaders: Record<string, unknown>[];
  statKey: string;
}) {
  const textColor =
    color === "pass"
      ? "text-pass"
      : color === "rush"
        ? "text-rush"
        : "text-rec";

  if (leaders.length === 0) return null;

  return (
    <div className="mb-4 rounded-lg border border-border bg-smoke p-3">
      <div className={`mb-2 font-heading text-xs font-bold uppercase ${textColor}`}>
        {title}
      </div>
      {leaders.map((l, i) => (
        <div
          key={String(l.player_id)}
          className="flex items-baseline justify-between border-b border-border/30 py-1.5 last:border-0"
        >
          <Link
            href={`/players/${l.player_id}`}
            className="text-sm text-text hover:text-gold"
          >
            {i + 1}. {String(l.player_name)}
          </Link>
          <span className={`font-mono text-sm font-bold ${textColor}`}>
            {Number(l[statKey]).toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}
