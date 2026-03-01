export const dynamic = "force-dynamic";

import Link from "next/link";
import { notFound } from "next/navigation";
import { getDraftByYear } from "@/lib/queries";

export async function generateMetadata({ params }: { params: Promise<{ year: string }> }) {
  const { year } = await params;
  return { title: `${year} NFL Draft | Saints Encyclopedia` };
}

export default async function DraftYearPage({
  params,
}: {
  params: Promise<{ year: string }>;
}) {
  const { year } = await params;
  const yearNum = parseInt(year, 10);
  if (isNaN(yearNum)) notFound();

  const picks = await getDraftByYear(yearNum);
  if (picks.length === 0) notFound();

  // Group by round
  const rounds = new Map<number, typeof picks>();
  for (const pick of picks) {
    const arr = rounds.get(pick.round) || [];
    arr.push(pick);
    rounds.set(pick.round, arr);
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      {/* Breadcrumb */}
      <div className="mb-4 font-body text-sm text-dim">
        <Link href="/draft" className="hover:text-gold">
          Draft History
        </Link>{" "}
        &rsaquo; {yearNum}
      </div>

      <h1 className="mb-6 font-heading text-3xl font-bold text-gold">
        {yearNum} NFL DRAFT
      </h1>
      <p className="mb-8 font-body text-dim">
        {picks.length} selections by the New Orleans Saints
      </p>

      {/* Draft picks table */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full font-mono text-sm">
          <thead>
            <tr className="border-b border-border bg-smoke text-dim">
              <th className="px-3 py-2 text-left font-heading text-xs uppercase">Rd</th>
              <th className="px-3 py-2 text-left font-heading text-xs uppercase">Pick</th>
              <th className="px-3 py-2 text-left font-heading text-xs uppercase">Player</th>
              <th className="px-3 py-2 text-left font-heading text-xs uppercase">Pos</th>
              <th className="px-3 py-2 text-left font-heading text-xs uppercase">College</th>
            </tr>
          </thead>
          <tbody>
            {Array.from(rounds.entries()).map(([round, roundPicks]) => (
              roundPicks.map((pick, idx) => (
                <tr
                  key={pick.pick}
                  className={`border-b border-border/50 ${idx === 0 && round > 1 ? "border-t-2 border-t-border" : ""}`}
                >
                  <td className="px-3 py-2 font-bold text-gold">{pick.round}</td>
                  <td className="px-3 py-2 text-text">{pick.pick}</td>
                  <td className="px-3 py-2 font-bold text-text">
                    {pick.linked_player_id ? (
                      <Link href={`/players/${pick.linked_player_id}`} className="text-gold hover:underline">
                        {pick.player_name}
                      </Link>
                    ) : (
                      pick.player_name
                    )}
                  </td>
                  <td className="px-3 py-2 text-dim">{pick.position}</td>
                  <td className="px-3 py-2 text-dim">{pick.college}</td>
                </tr>
              ))
            ))}
          </tbody>
        </table>
      </div>

      {/* Navigation */}
      <div className="mt-6 flex justify-between text-sm">
        {yearNum > 1967 ? (
          <Link href={`/draft/${yearNum - 1}`} className="font-body text-gold hover:underline">
            &larr; {yearNum - 1} Draft
          </Link>
        ) : <span />}
        {yearNum < new Date().getFullYear() ? (
          <Link href={`/draft/${yearNum + 1}`} className="font-body text-gold hover:underline">
            {yearNum + 1} Draft &rarr;
          </Link>
        ) : <span />}
      </div>
    </div>
  );
}
