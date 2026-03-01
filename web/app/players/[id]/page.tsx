export const dynamic = "force-dynamic";

import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getPlayer,
  getPlayerCareerPassing,
  getPlayerCareerRushing,
  getPlayerCareerReceiving,
  getPlayerSeasonStats,
  getPlayerSeasonRushing,
  getPlayerSeasonReceiving,
  getPlayerGameLog,
  getPlayerDraftInfo,
} from "@/lib/queries";
import {
  SeasonPassingTable,
  SeasonRushingTable,
  SeasonReceivingTable,
  PlayerGameLogTable,
} from "@/components/player-profile-tables";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const player = await getPlayer(id);
  if (!player) return { title: "Player Not Found" };
  return { title: `${player.player_name} | Saints Encyclopedia` };
}

export default async function PlayerProfilePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const player = await getPlayer(id);
  if (!player) notFound();

  const [
    careerPassing,
    careerRushing,
    careerReceiving,
    rawSeasonPassing,
    rawSeasonRushing,
    rawSeasonReceiving,
    rawGameLog,
    draftInfo,
  ] = await Promise.all([
    getPlayerCareerPassing(id),
    getPlayerCareerRushing(id),
    getPlayerCareerReceiving(id),
    getPlayerSeasonStats(id),
    getPlayerSeasonRushing(id),
    getPlayerSeasonReceiving(id),
    getPlayerGameLog(id),
    getPlayerDraftInfo(id),
  ]);

  const hasPassing = careerPassing && Number(careerPassing.att) > 0;
  const hasRushing = careerRushing && Number(careerRushing.att) > 0;
  const hasReceiving = careerReceiving && Number(careerReceiving.rec) > 0;

  const seasonPassing = JSON.parse(JSON.stringify(rawSeasonPassing));
  const seasonRushing = JSON.parse(JSON.stringify(rawSeasonRushing));
  const seasonReceiving = JSON.parse(JSON.stringify(rawSeasonReceiving));
  const gameLog = JSON.parse(JSON.stringify(rawGameLog));

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      {/* Header */}
      <div className="mb-8">
        <div className="mb-1 font-body text-sm text-dim">
          <Link href="/players" className="hover:text-gold">
            Players
          </Link>{" "}
          &rsaquo;
        </div>
        <h1 className="font-heading text-4xl font-bold text-gold">
          {player.player_name.toUpperCase()}
        </h1>
        {(hasPassing || hasRushing || hasReceiving) && (
          <p className="mt-1 font-mono text-sm text-dim">
            {hasPassing ? `${careerPassing!.first_season}` : hasRushing ? `${careerRushing!.first_season}` : `${careerReceiving!.first_season}`}
            –
            {hasPassing ? `${careerPassing!.last_season}` : hasRushing ? `${careerRushing!.last_season}` : `${careerReceiving!.last_season}`}
          </p>
        )}
      </div>

      {/* Bio Card */}
      {(player.position || player.college || player.seasons_text || draftInfo) && (
        <div className="mb-8 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-gold/30 bg-smoke px-5 py-4 font-body text-sm">
          {player.position && (
            <span className="font-heading text-lg font-bold text-gold">
              {player.position}
            </span>
          )}
          {player.college && (
            <span className="text-dim">
              <span className="text-dim/60">College:</span>{" "}
              <span className="text-text">{player.college}</span>
            </span>
          )}
          {player.seasons_text && (
            <span className="text-dim">
              <span className="text-dim/60">Saints:</span>{" "}
              <span className="text-text">{player.seasons_text}</span>
            </span>
          )}
          {draftInfo && (
            <span className="text-dim">
              <span className="text-dim/60">Draft:</span>{" "}
              <span className="text-text">
                {draftInfo.season} Rd {draftInfo.round}, Pick {draftInfo.pick}
              </span>
            </span>
          )}
          {player.height && (
            <span className="text-dim">
              <span className="text-dim/60">Ht:</span>{" "}
              <span className="text-text">{player.height}</span>
            </span>
          )}
          {player.weight && (
            <span className="text-dim">
              <span className="text-dim/60">Wt:</span>{" "}
              <span className="text-text">{player.weight}</span>
            </span>
          )}
        </div>
      )}

      {/* Career Stats Cards */}
      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {hasPassing && (
          <CareerCard
            title="CAREER PASSING"
            color="pass"
            stats={[
              { label: "Games", value: careerPassing.games },
              { label: "Comp", value: Number(careerPassing.com).toLocaleString() },
              { label: "Att", value: Number(careerPassing.att).toLocaleString() },
              { label: "Yards", value: Number(careerPassing.yds).toLocaleString() },
              { label: "TD", value: careerPassing.td },
              { label: "INT", value: careerPassing.int_thrown },
            ]}
          />
        )}
        {hasRushing && (
          <CareerCard
            title="CAREER RUSHING"
            color="rush"
            stats={[
              { label: "Games", value: careerRushing.games },
              { label: "Att", value: Number(careerRushing.att).toLocaleString() },
              { label: "Yards", value: Number(careerRushing.yds).toLocaleString() },
              { label: "TD", value: careerRushing.td },
            ]}
          />
        )}
        {hasReceiving && (
          <CareerCard
            title="CAREER RECEIVING"
            color="rec"
            stats={[
              { label: "Games", value: careerReceiving.games },
              { label: "Rec", value: Number(careerReceiving.rec).toLocaleString() },
              { label: "Yards", value: Number(careerReceiving.yds).toLocaleString() },
              { label: "TD", value: careerReceiving.td },
            ]}
          />
        )}
      </div>

      {/* Season-by-Season Breakdown */}
      {hasPassing && seasonPassing.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-3 font-heading text-lg font-bold text-pass">
            PASSING BY SEASON
          </h2>
          <div className="rounded-lg border border-pass/30">
            <SeasonPassingTable data={seasonPassing} />
          </div>
        </div>
      )}

      {hasRushing && seasonRushing.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-3 font-heading text-lg font-bold text-rush">
            RUSHING BY SEASON
          </h2>
          <div className="rounded-lg border border-rush/30">
            <SeasonRushingTable data={seasonRushing} />
          </div>
        </div>
      )}

      {hasReceiving && seasonReceiving.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-3 font-heading text-lg font-bold text-rec">
            RECEIVING BY SEASON
          </h2>
          <div className="rounded-lg border border-rec/30">
            <SeasonReceivingTable data={seasonReceiving} />
          </div>
        </div>
      )}

      {/* Game Log */}
      {gameLog.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 font-heading text-lg font-bold text-text">
            GAME LOG ({gameLog.length} games)
          </h2>
          <div className="rounded-lg border border-border">
            <PlayerGameLogTable
              data={gameLog}
              hasPassing={!!hasPassing}
              hasRushing={!!hasRushing}
              hasReceiving={!!hasReceiving}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function CareerCard({
  title,
  color,
  stats,
}: {
  title: string;
  color: string;
  stats: { label: string; value: unknown }[];
}) {
  const borderColor =
    color === "pass"
      ? "border-pass/30"
      : color === "rush"
        ? "border-rush/30"
        : "border-rec/30";
  const textColor =
    color === "pass" ? "text-pass" : color === "rush" ? "text-rush" : "text-rec";

  return (
    <div className={`rounded-lg border ${borderColor} bg-smoke p-4`}>
      <h3 className={`mb-3 font-heading text-xs font-bold uppercase ${textColor}`}>
        {title}
      </h3>
      <div className="grid grid-cols-3 gap-3">
        {stats.map((s) => (
          <div key={s.label}>
            <div className="font-heading text-[10px] uppercase tracking-wider text-dim">
              {s.label}
            </div>
            <div className="font-mono text-lg font-bold text-text">
              {String(s.value)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
