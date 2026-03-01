export const metadata = {
  title: "About | Saints Encyclopedia",
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <h1 className="mb-6 font-heading text-4xl font-bold text-gold">ABOUT</h1>

      <div className="space-y-6 font-body text-text leading-relaxed">
        <p>
          Saints Encyclopedia is a comprehensive statistical database covering
          every New Orleans Saints season from 1967 to the present. It includes
          box scores, player stats, draft history, and career records for the
          entire franchise.
        </p>

        <h2 className="font-heading text-xl font-bold text-gold">
          DATA SOURCES
        </h2>
        <p>
          Game-by-game statistics are sourced from{" "}
          <span className="text-gold">Pro Football Archives</span>{" "}
          (profootballarchives.com), which provides detailed historical box
          scores going back to the franchise&apos;s inaugural season. For recent
          seasons not yet covered by PFA, data is pulled from{" "}
          <span className="text-gold">FootballDB</span> (footballdb.com) as a
          fallback.
        </p>
        <p>
          The all-time roster and player biographical information (position,
          college, height, weight) come from FootballDB&apos;s all-time roster
          pages. Draft history is also sourced from FootballDB.
        </p>

        <h2 className="font-heading text-xl font-bold text-gold">
          WHAT&apos;S INCLUDED
        </h2>
        <ul className="list-inside list-disc space-y-2 text-dim">
          <li>
            <span className="text-text">Game scores and results</span> &mdash;
            every regular season and playoff game
          </li>
          <li>
            <span className="text-text">Passing, rushing, and receiving</span>{" "}
            &mdash; individual player stats per game
          </li>
          <li>
            <span className="text-text">Defensive stats</span> &mdash; tackles,
            sacks (1973+), interceptions (1967+), and detailed defense (1999+)
          </li>
          <li>
            <span className="text-text">Draft picks</span> &mdash; every Saints
            draft selection, 1967 to present
          </li>
          <li>
            <span className="text-text">Career and season records</span>{" "}
            &mdash; leaderboards across all major categories
          </li>
        </ul>

        <h2 className="font-heading text-xl font-bold text-gold">
          COVERAGE NOTES
        </h2>
        <p className="text-dim">
          Defensive statistics vary by era. Sack records begin in 1973 when the
          NFL started officially tracking them. Interception records go back to
          the franchise&apos;s founding in 1967.
        </p>

        <h2 className="font-heading text-xl font-bold text-gold">
          ASK AI
        </h2>
        <p>
          The{" "}
          <span className="text-gold">Ask AI</span> feature lets you ask
          natural-language questions about Saints history and stats. It queries
          the database directly and can answer questions like &ldquo;Who led
          the Saints in passing in 2009?&rdquo; or &ldquo;How many games did
          the Saints win in their first season?&rdquo;
        </p>
      </div>
    </div>
  );
}
