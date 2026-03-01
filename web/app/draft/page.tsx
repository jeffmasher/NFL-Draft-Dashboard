export const dynamic = "force-dynamic";

import Link from "next/link";
import { getDraftYears } from "@/lib/queries";

export const metadata = { title: "Draft History | Saints Encyclopedia" };

export default async function DraftIndexPage() {
  const drafts = await getDraftYears();

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <h1 className="mb-6 font-heading text-3xl font-bold text-gold">
        DRAFT HISTORY
      </h1>
      <p className="mb-8 font-body text-dim">
        {drafts.length} drafts of New Orleans Saints selections (
        {drafts[drafts.length - 1]?.season}–{drafts[0]?.season})
      </p>

      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {drafts.map((d) => (
          <Link
            key={d.season}
            href={`/draft/${d.season}`}
            className="group rounded-lg border border-border bg-panel p-4 transition-colors hover:border-gold/30"
          >
            <div className="flex items-baseline justify-between">
              <span className="font-heading text-2xl font-bold text-gold">
                {d.season}
              </span>
              <span className="font-mono text-xs text-dim">
                {d.picks} picks
              </span>
            </div>
            <div className="mt-2 font-body text-sm text-text">
              1st pick: #{d.first_pick}
            </div>
            <div className="mt-1 font-mono text-xs text-dim truncate">
              {d.first_player}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
