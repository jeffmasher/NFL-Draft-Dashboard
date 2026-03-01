export const dynamic = "force-dynamic";

import Link from "next/link";
import { getPlayersWithStats, searchPlayers } from "@/lib/queries";
import { Search } from "@/components/search";
import { PlayersStatsTable, PlayersSearchTable } from "@/components/players-table";

export const metadata = { title: "Players | Saints Encyclopedia" };

export default async function PlayersPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;

  const rawPlayers = q
    ? await searchPlayers(q, 100)
    : await getPlayersWithStats(200, 0);

  const players = JSON.parse(JSON.stringify(rawPlayers));

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="font-heading text-3xl font-bold text-gold">PLAYERS</h1>
        <Search placeholder="Search by name..." />
      </div>

      {q && (
        <p className="mb-4 font-body text-sm text-dim">
          {players.length} results for &ldquo;{q}&rdquo;
          <Link href="/players" className="ml-2 text-gold hover:underline">
            Clear
          </Link>
        </p>
      )}

      <div className="rounded-lg border border-border">
        {!q ? (
          <PlayersStatsTable data={players} />
        ) : (
          <PlayersSearchTable data={players} />
        )}
      </div>

      {players.length === 0 && (
        <div className="py-12 text-center font-body text-dim">
          No players found.
        </div>
      )}
    </div>
  );
}
