export const dynamic = "force-dynamic";

import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getGame,
  getGameTeamStats,
  getScoringPlays,
  getGamePassing,
  getGameRushing,
  getGameReceiving,
  getGameDefense,
  getGameSacks,
  getGameInterceptions,
} from "@/lib/queries";
import { GamePassingTable, GameRushingTable, GameReceivingTable } from "@/components/game-tables";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const game = await getGame(id);
  if (!game) return { title: "Game Not Found" };
  const ha = game.home_away === "home" ? "vs" : "@";
  return {
    title: `Saints ${ha} ${game.opponent} (${game.game_date}) | Saints Encyclopedia`,
  };
}

/** Strip trailing team abbreviation from team names: "Las Vegas RaidersLV" → "Las Vegas Raiders" */
function cleanTeamName(team: string): string {
  return team.replace(/[A-Z]{2,4}$/, "").trim();
}

/** Clean up scraped scoring play descriptions that have run-together text. */
function cleanDescription(desc: string): string {
  return desc
    // Separate run-together letters→digits: "Kamara6" → "Kamara 6"
    .replace(/([a-zA-Z])(\d)/g, "$1 $2")
    // Separate run-together digits→letters: "50FG" → "50 FG"
    .replace(/(\d)([a-zA-Z])/g, "$1 $2")
    // Separate camelCase: "LutzKick" → "Lutz Kick"
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    // Separate "kick" from preceding name: "Lutzkick" → "Lutz kick"
    .replace(/([a-z])(kick|pass|run|return|good|blocked|failed|safety)/gi, "$1 $2")
    // Space before parens: "FG(" → "FG ("
    .replace(/([^\s(])(\()/g, "$1 $2")
    // Remove ALL team-name parentheticals at end: "(Tennessee TitansTEN)", "(New Orleans SaintsNO)", etc.
    .replace(/\s*\([^)]*[A-Z]{2,3}\)\s*$/, "")
    // Insert "-yard" after numbers before play types: "50 FG" → "50-yard FG"
    .replace(/(\d+)\s+(FG|run|pass|punt return|kick return|fumble return|interception return|punt|fumble)/gi, "$1-yard $2")
    .replace(/\s{2,}/g, " ")
    .trim();
}

export default async function GamePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const game = await getGame(id);
  if (!game) notFound();

  const [
    teamStats,
    scoringPlays,
    rawPassing,
    rawRushing,
    rawReceiving,
    defense,
    sacks,
    interceptions,
  ] = await Promise.all([
    getGameTeamStats(id),
    getScoringPlays(id),
    getGamePassing(id),
    getGameRushing(id),
    getGameReceiving(id),
    getGameDefense(id),
    getGameSacks(id),
    getGameInterceptions(id),
  ]);

  const saintsStats = teamStats.find(
    (t) => t.team.includes("Saints") || t.team.includes("New Orleans")
  );
  const oppStats = teamStats.find(
    (t) => !t.team.includes("Saints") && !t.team.includes("New Orleans")
  );

  const isSaintsTeam = (team: string) =>
    team.includes("Saints") || team.includes("New Orleans");

  const passing = JSON.parse(JSON.stringify(rawPassing));
  const rushing = JSON.parse(JSON.stringify(rawRushing));
  const receiving = JSON.parse(JSON.stringify(rawReceiving));

  const saintsPassers = passing.filter((p: Record<string, unknown>) => isSaintsTeam(String(p.team)));
  const oppPassers = passing.filter((p: Record<string, unknown>) => !isSaintsTeam(String(p.team)));
  const saintsRushers = rushing.filter((p: Record<string, unknown>) => isSaintsTeam(String(p.team)));
  const oppRushers = rushing.filter((p: Record<string, unknown>) => !isSaintsTeam(String(p.team)));
  const saintsReceivers = receiving.filter((p: Record<string, unknown>) => isSaintsTeam(String(p.team)));
  const oppReceivers = receiving.filter((p: Record<string, unknown>) => !isSaintsTeam(String(p.team)));

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      {/* Breadcrumb */}
      <div className="mb-4 font-body text-sm text-dim">
        <Link href="/seasons" className="hover:text-gold">
          Seasons
        </Link>{" "}
        &rsaquo;{" "}
        <Link href={`/seasons/${game.season}`} className="hover:text-gold">
          {game.season}
        </Link>{" "}
        &rsaquo; Game
      </div>

      {/* Score Header */}
      <div className="mb-8 rounded-xl border border-border bg-panel p-6">
        <div className="mb-2 font-mono text-xs text-dim">
          {game.game_date} &middot;{" "}
          {game.game_type !== "regular" && (
            <span className="uppercase text-gold">{game.game_type} &middot; </span>
          )}
          {game.venue && <>{game.venue} &middot; </>}
          {game.attendance && `Att: ${game.attendance.toLocaleString()}`}
        </div>
        <div className="flex items-center justify-center gap-8">
          <div className="flex flex-col items-center">
            <span className="font-heading text-sm font-bold uppercase text-gold">
              Saints
            </span>
            <span className="font-mono text-4xl font-bold text-text">
              {game.saints_score}
            </span>
          </div>
          <div className="flex flex-col items-center">
            <span
              className={`rounded px-3 py-1 font-heading text-sm font-bold ${
                game.result === "W"
                  ? "bg-rush/20 text-rush"
                  : game.result === "L"
                    ? "bg-rec/20 text-rec"
                    : "bg-muted/20 text-muted"
              }`}
            >
              {game.result === "W" ? "WIN" : game.result === "L" ? "LOSS" : "TIE"}
            </span>
            <span className="mt-1 font-mono text-xs text-dim">
              {game.home_away === "home" ? "vs" : "@"}
            </span>
          </div>
          <div className="flex flex-col items-center">
            <span className="font-heading text-sm font-bold uppercase text-dim">
              {game.opponent}
            </span>
            <span className="font-mono text-4xl font-bold text-dim">
              {game.opponent_score}
            </span>
          </div>
        </div>
      </div>

      {/* Team Stats Comparison */}
      {saintsStats && oppStats && (
        <div className="mb-8">
          <h2 className="mb-3 font-heading text-lg font-bold text-text">
            TEAM STATS
          </h2>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full font-mono text-sm">
              <thead>
                <tr className="border-b border-border text-dim">
                  <th className="px-3 py-2 text-right font-medium">Saints</th>
                  <th className="px-3 py-2 text-center font-medium">Stat</th>
                  <th className="px-3 py-2 text-left font-medium">
                    {game.opponent}
                  </th>
                </tr>
              </thead>
              <tbody>
                <CompRow label="Rush Att-Yds" saints={`${saintsStats.rush_att}-${saintsStats.rush_yds}`} opp={`${oppStats.rush_att}-${oppStats.rush_yds}`} />
                <CompRow label="Rush TD" saints={saintsStats.rush_td} opp={oppStats.rush_td} />
                <CompRow label="Pass Comp-Att" saints={`${saintsStats.pass_com}-${saintsStats.pass_att}`} opp={`${oppStats.pass_com}-${oppStats.pass_att}`} />
                <CompRow label="Pass Yds" saints={saintsStats.pass_yds} opp={oppStats.pass_yds} />
                <CompRow label="Pass TD" saints={saintsStats.pass_td} opp={oppStats.pass_td} />
                <CompRow label="INT" saints={saintsStats.pass_int} opp={oppStats.pass_int} />
                <CompRow label="Sacks" saints={saintsStats.sacks} opp={oppStats.sacks} />
                <CompRow label="Interceptions" saints={saintsStats.interceptions} opp={oppStats.interceptions} />
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Scoring Plays */}
      {scoringPlays.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-3 font-heading text-lg font-bold text-text">
            SCORING PLAYS
          </h2>
          <div className="rounded-lg border border-border">
            {scoringPlays.map((play) => (
              <div
                key={play.id}
                className="flex items-start gap-3 border-b border-border/50 px-4 py-3 last:border-0"
              >
                <span className="rounded bg-panel px-2 py-0.5 font-mono text-xs text-dim">
                  Q{play.quarter}
                </span>
                <div className="flex-1">
                  <span className="font-body text-sm text-text">
                    {cleanDescription(play.description)}
                  </span>
                  <span className="ml-2 font-mono text-xs text-dim">
                    ({cleanTeamName(String(play.team))})
                  </span>
                </div>
                <span className="font-mono text-sm font-bold text-gold">
                  {play.saints_score}-{play.opp_score}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Player Stats */}
      <div className="grid gap-8 lg:grid-cols-2">
        {/* Saints Stats */}
        <div>
          <h2 className="mb-4 font-heading text-xl font-bold text-gold">SAINTS</h2>
          {saintsPassers.length > 0 && (
            <StatSection title="PASSING" color="pass">
              <GamePassingTable data={saintsPassers} linkPlayers={true} />
            </StatSection>
          )}
          {saintsRushers.length > 0 && (
            <StatSection title="RUSHING" color="rush">
              <GameRushingTable data={saintsRushers} linkPlayers={true} />
            </StatSection>
          )}
          {saintsReceivers.length > 0 && (
            <StatSection title="RECEIVING" color="rec">
              <GameReceivingTable data={saintsReceivers} linkPlayers={true} />
            </StatSection>
          )}
        </div>

        {/* Opponent Stats */}
        <div>
          <h2 className="mb-4 font-heading text-xl font-bold text-dim">
            {game.opponent.toUpperCase()}
          </h2>
          {oppPassers.length > 0 && (
            <StatSection title="PASSING" color="pass">
              <GamePassingTable data={oppPassers} linkPlayers={false} />
            </StatSection>
          )}
          {oppRushers.length > 0 && (
            <StatSection title="RUSHING" color="rush">
              <GameRushingTable data={oppRushers} linkPlayers={false} />
            </StatSection>
          )}
          {oppReceivers.length > 0 && (
            <StatSection title="RECEIVING" color="rec">
              <GameReceivingTable data={oppReceivers} linkPlayers={false} />
            </StatSection>
          )}
        </div>
      </div>
    </div>
  );
}

function CompRow({ label, saints, opp }: { label: string; saints: string | number; opp: string | number }) {
  return (
    <tr className="border-b border-border/50">
      <td className="px-3 py-2 text-right font-mono text-text">{saints}</td>
      <td className="px-3 py-2 text-center font-heading text-xs uppercase text-dim">{label}</td>
      <td className="px-3 py-2 text-left font-mono text-text">{opp}</td>
    </tr>
  );
}

function StatSection({ title, color, children }: { title: string; color: string; children: React.ReactNode }) {
  const borderColor = color === "pass" ? "border-pass/30" : color === "rush" ? "border-rush/30" : "border-rec/30";
  const textColor = color === "pass" ? "text-pass" : color === "rush" ? "text-rush" : "text-rec";
  return (
    <div className={`mb-4 rounded-lg border ${borderColor} bg-smoke`}>
      <div className={`px-3 py-2 font-heading text-xs font-bold uppercase ${textColor}`}>{title}</div>
      {children}
    </div>
  );
}
