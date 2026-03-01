import { query, queryOne } from "./db";

// ── Types ──────────────────────────────────────────────

export interface Game {
  game_id: string;
  season: number;
  game_date: string;
  day_of_week: string | null;
  game_type: string;
  opponent: string;
  opponent_abbr: string | null;
  home_away: string;
  saints_score: number | null;
  opponent_score: number | null;
  result: string | null;
  location: string | null;
  venue: string | null;
  attendance: number | null;
  boxscore_url: string | null;
}

export interface SeasonSummary {
  season: number;
  wins: number;
  losses: number;
  ties: number;
  games: number;
  points_for: number;
  points_against: number;
}

export interface Player {
  player_id: string;
  player_name: string;
  pfa_url: string | null;
  position: string | null;
  college: string | null;
  height: string | null;
  weight: number | null;
  birth_date: string | null;
  fdb_id: string | null;
  fdb_url: string | null;
  seasons_text: string | null;
}

export interface TeamGameStats {
  game_id: string;
  team: string;
  rush_att: number;
  rush_yds: number;
  rush_td: number;
  pass_att: number;
  pass_com: number;
  pass_yds: number;
  pass_td: number;
  pass_int: number;
  times_sacked: number;
  sack_yds_lost: number;
  sacks: number;
  interceptions: number;
  punt_count: number;
  punt_yds: number;
  total_points: number;
}

export interface ScoringPlay {
  id: number;
  game_id: string;
  quarter: number;
  team: string;
  description: string;
  saints_score: number;
  opp_score: number;
}

export interface PassingStats {
  game_id: string;
  player_id: string;
  player_name: string;
  team: string;
  att: number;
  com: number;
  pct: number;
  int_thrown: number;
  yds: number;
  avg: number;
  lg: number;
  td: number;
  sacked: number;
  sacked_yds: number;
  rtg: number;
}

export interface RushingStats {
  game_id: string;
  player_id: string;
  player_name: string;
  team: string;
  att: number;
  yds: number;
  avg: number;
  lg: number;
  td: number;
}

export interface ReceivingStats {
  game_id: string;
  player_id: string;
  player_name: string;
  team: string;
  tar: number;
  rec: number;
  yds: number;
  avg: number;
  lg: number;
  td: number;
}

export interface DefenseStats {
  game_id: string;
  player_id: string;
  player_name: string;
  team: string;
  tkl: number;
  tfl: number;
  qh: number;
  pd: number;
  ff: number;
  bl: number;
}

export interface SackStats {
  game_id: string;
  player_id: string;
  player_name: string;
  team: string;
  sacks: number;
  yds: number;
}

export interface InterceptionStats {
  game_id: string;
  player_id: string;
  player_name: string;
  team: string;
  int_count: number;
  yds: number;
  avg: number;
  lg: number;
  td: number;
}

// ── Franchise summary ──────────────────────────────────

export async function getFranchiseSummary() {
  const row = await queryOne<{
    total_games: number;
    wins: number;
    losses: number;
    ties: number;
    first_season: number;
    last_season: number;
    total_players: number;
    points_for: number;
    points_against: number;
  }>(`
    SELECT
      COUNT(*) as total_games,
      SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) as wins,
      SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) as losses,
      SUM(CASE WHEN result = 'T' THEN 1 ELSE 0 END) as ties,
      MIN(season) as first_season,
      MAX(season) as last_season,
      (SELECT COUNT(*) FROM players WHERE pfa_url IS NOT NULL) as total_players,
      COALESCE(SUM(saints_score), 0) as points_for,
      COALESCE(SUM(opponent_score), 0) as points_against
    FROM games
    WHERE game_type = 'regular'
  `);
  return row;
}

// ── Seasons ────────────────────────────────────────────

export async function getSeasons(): Promise<SeasonSummary[]> {
  return query<SeasonSummary>(`
    SELECT
      season,
      SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) as wins,
      SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) as losses,
      SUM(CASE WHEN result = 'T' THEN 1 ELSE 0 END) as ties,
      COUNT(*) as games,
      COALESCE(SUM(saints_score), 0) as points_for,
      COALESCE(SUM(opponent_score), 0) as points_against
    FROM games
    WHERE game_type = 'regular'
    GROUP BY season
    ORDER BY season DESC
  `);
}

export async function getSeasonGames(year: number): Promise<Game[]> {
  return query<Game>(
    `SELECT * FROM games WHERE season = ? ORDER BY game_date`,
    [year]
  );
}

export async function getSeasonTeamStats(year: number) {
  return query<{
    rush_att: number;
    rush_yds: number;
    rush_td: number;
    pass_att: number;
    pass_com: number;
    pass_yds: number;
    pass_td: number;
    pass_int: number;
    total_points: number;
  }>(`
    SELECT
      COALESCE(SUM(t.rush_att), 0) as rush_att,
      COALESCE(SUM(t.rush_yds), 0) as rush_yds,
      COALESCE(SUM(t.rush_td), 0) as rush_td,
      COALESCE(SUM(t.pass_att), 0) as pass_att,
      COALESCE(SUM(t.pass_com), 0) as pass_com,
      COALESCE(SUM(t.pass_yds), 0) as pass_yds,
      COALESCE(SUM(t.pass_td), 0) as pass_td,
      COALESCE(SUM(t.pass_int), 0) as pass_int,
      COALESCE(SUM(t.total_points), 0) as total_points
    FROM team_game_stats t
    JOIN games g ON t.game_id = g.game_id
    WHERE g.season = ?
      AND (t.team LIKE '%Saints%' OR t.team LIKE '%New Orleans%')
      AND g.game_type = 'regular'
  `, [year]);
}

export async function getSeasonPassingLeaders(year: number) {
  return query(`
    SELECT p.player_id, p.player_name,
      SUM(pp.att) as att, SUM(pp.com) as com, SUM(pp.yds) as yds,
      SUM(pp.td) as td, SUM(pp.int_thrown) as int_thrown,
      COUNT(*) as games
    FROM player_passing pp
    JOIN players p ON pp.player_id = p.player_id
    JOIN games g ON pp.game_id = g.game_id
    WHERE g.season = ? AND g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    GROUP BY pp.player_id
    ORDER BY yds DESC
    LIMIT 5
  `, [year]);
}

export async function getSeasonRushingLeaders(year: number) {
  return query(`
    SELECT p.player_id, p.player_name,
      SUM(pr.att) as att, SUM(pr.yds) as yds, SUM(pr.td) as td,
      COUNT(*) as games
    FROM player_rushing pr
    JOIN players p ON pr.player_id = p.player_id
    JOIN games g ON pr.game_id = g.game_id
    WHERE g.season = ? AND g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    GROUP BY pr.player_id
    ORDER BY yds DESC
    LIMIT 5
  `, [year]);
}

export async function getSeasonReceivingLeaders(year: number) {
  return query(`
    SELECT p.player_id, p.player_name,
      SUM(pr.rec) as rec, SUM(pr.yds) as yds, SUM(pr.td) as td,
      COUNT(*) as games
    FROM player_receiving pr
    JOIN players p ON pr.player_id = p.player_id
    JOIN games g ON pr.game_id = g.game_id
    WHERE g.season = ? AND g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    GROUP BY pr.player_id
    ORDER BY yds DESC
    LIMIT 5
  `, [year]);
}

// ── Games (Box Scores) ────────────────────────────────

export async function getGame(id: string): Promise<Game | null> {
  return queryOne<Game>(`SELECT * FROM games WHERE game_id = ?`, [id]);
}

export async function getGameTeamStats(gameId: string): Promise<TeamGameStats[]> {
  return query<TeamGameStats>(
    `SELECT * FROM team_game_stats WHERE game_id = ?`,
    [gameId]
  );
}

export async function getScoringPlays(gameId: string): Promise<ScoringPlay[]> {
  return query<ScoringPlay>(
    `SELECT * FROM scoring_plays WHERE game_id = ? ORDER BY id`,
    [gameId]
  );
}

export async function getGamePassing(gameId: string): Promise<PassingStats[]> {
  return query<PassingStats>(`
    SELECT pp.*, p.player_name
    FROM player_passing pp
    JOIN players p ON pp.player_id = p.player_id
    WHERE pp.game_id = ?
    ORDER BY pp.yds DESC
  `, [gameId]);
}

export async function getGameRushing(gameId: string): Promise<RushingStats[]> {
  return query<RushingStats>(`
    SELECT pr.*, p.player_name
    FROM player_rushing pr
    JOIN players p ON pr.player_id = p.player_id
    WHERE pr.game_id = ?
    ORDER BY pr.yds DESC
  `, [gameId]);
}

export async function getGameReceiving(gameId: string): Promise<ReceivingStats[]> {
  return query<ReceivingStats>(`
    SELECT pr.*, p.player_name
    FROM player_receiving pr
    JOIN players p ON pr.player_id = p.player_id
    WHERE pr.game_id = ?
    ORDER BY pr.yds DESC
  `, [gameId]);
}

export async function getGameDefense(gameId: string): Promise<DefenseStats[]> {
  return query<DefenseStats>(`
    SELECT pd.*, p.player_name
    FROM player_defense pd
    JOIN players p ON pd.player_id = p.player_id
    WHERE pd.game_id = ?
    ORDER BY pd.tkl DESC
  `, [gameId]);
}

export async function getGameSacks(gameId: string): Promise<SackStats[]> {
  return query<SackStats>(`
    SELECT ps.*, p.player_name
    FROM player_sacks ps
    JOIN players p ON ps.player_id = p.player_id
    WHERE ps.game_id = ?
    ORDER BY ps.sacks DESC
  `, [gameId]);
}

export async function getGameInterceptions(gameId: string): Promise<InterceptionStats[]> {
  return query<InterceptionStats>(`
    SELECT pi.*, p.player_name
    FROM player_interceptions pi
    JOIN players p ON pi.player_id = p.player_id
    WHERE pi.game_id = ?
    ORDER BY pi.yds DESC
  `, [gameId]);
}

// ── Players ────────────────────────────────────────────

export async function searchPlayers(q: string, limit = 50) {
  return query(`
    SELECT DISTINCT p.player_id, p.player_name, p.position,
      (SELECT MIN(g.season) FROM player_passing pp JOIN games g ON pp.game_id = g.game_id WHERE pp.player_id = p.player_id
       UNION ALL
       SELECT MIN(g.season) FROM player_rushing pr JOIN games g ON pr.game_id = g.game_id WHERE pr.player_id = p.player_id
       UNION ALL
       SELECT MIN(g.season) FROM player_receiving pr JOIN games g ON pr.game_id = g.game_id WHERE pr.player_id = p.player_id
       ORDER BY 1 LIMIT 1
      ) as first_season,
      (SELECT MAX(g.season) FROM player_passing pp JOIN games g ON pp.game_id = g.game_id WHERE pp.player_id = p.player_id
       UNION ALL
       SELECT MAX(g.season) FROM player_rushing pr JOIN games g ON pr.game_id = g.game_id WHERE pr.player_id = p.player_id
       UNION ALL
       SELECT MAX(g.season) FROM player_receiving pr JOIN games g ON pr.game_id = g.game_id WHERE pr.player_id = p.player_id
       ORDER BY 1 DESC LIMIT 1
      ) as last_season
    FROM players p
    WHERE p.player_name LIKE ?
      AND p.pfa_url IS NOT NULL
    ORDER BY p.player_name
    LIMIT ?
  `, [`%${q}%`, limit]);
}

export async function getPlayersWithStats(limit = 100, offset = 0) {
  return query(`
    SELECT p.player_id, p.player_name, p.position,
      COALESCE(pass.yds, 0) as pass_yds,
      COALESCE(pass.td, 0) as pass_td,
      COALESCE(rush.yds, 0) as rush_yds,
      COALESCE(rush.td, 0) as rush_td,
      COALESCE(recv.yds, 0) as rec_yds,
      COALESCE(recv.td, 0) as rec_td,
      COALESCE(pass.games, 0) + COALESCE(rush.games, 0) + COALESCE(recv.games, 0) as stat_entries
    FROM players p
    LEFT JOIN (
      SELECT player_id, SUM(yds) as yds, SUM(td) as td, COUNT(DISTINCT game_id) as games
      FROM player_passing
      GROUP BY player_id
    ) pass ON p.player_id = pass.player_id
    LEFT JOIN (
      SELECT player_id, SUM(yds) as yds, SUM(td) as td, COUNT(DISTINCT game_id) as games
      FROM player_rushing
      GROUP BY player_id
    ) rush ON p.player_id = rush.player_id
    LEFT JOIN (
      SELECT player_id, SUM(yds) as yds, SUM(td) as td, COUNT(DISTINCT game_id) as games
      FROM player_receiving
      GROUP BY player_id
    ) recv ON p.player_id = recv.player_id
    WHERE COALESCE(pass.yds, 0) + COALESCE(rush.yds, 0) + COALESCE(recv.yds, 0) > 0
      AND p.pfa_url IS NOT NULL
    ORDER BY COALESCE(pass.yds, 0) + COALESCE(rush.yds, 0) + COALESCE(recv.yds, 0) DESC
    LIMIT ? OFFSET ?
  `, [limit, offset]);
}

export async function getPlayer(id: string) {
  return queryOne<Player>(`SELECT * FROM players WHERE player_id = ?`, [id]);
}

export async function getPlayerDraftInfo(playerId: string) {
  return queryOne<DraftPick>(`
    SELECT d.*
    FROM draft_picks d
    WHERE d.player_id = ?
       OR LOWER(d.player_name) = (SELECT LOWER(player_name) FROM players WHERE player_id = ?)
    LIMIT 1
  `, [playerId, playerId]);
}

export async function getPlayerCareerPassing(playerId: string) {
  return queryOne(`
    SELECT
      SUM(pp.att) as att, SUM(pp.com) as com, SUM(pp.yds) as yds,
      SUM(pp.td) as td, SUM(pp.int_thrown) as int_thrown,
      SUM(pp.sacked) as sacked,
      COUNT(DISTINCT pp.game_id) as games,
      MIN(g.season) as first_season, MAX(g.season) as last_season
    FROM player_passing pp
    JOIN games g ON pp.game_id = g.game_id
    WHERE pp.player_id = ?
  `, [playerId]);
}

export async function getPlayerCareerRushing(playerId: string) {
  return queryOne(`
    SELECT
      SUM(pr.att) as att, SUM(pr.yds) as yds, SUM(pr.td) as td,
      COUNT(DISTINCT pr.game_id) as games,
      MIN(g.season) as first_season, MAX(g.season) as last_season
    FROM player_rushing pr
    JOIN games g ON pr.game_id = g.game_id
    WHERE pr.player_id = ?
  `, [playerId]);
}

export async function getPlayerCareerReceiving(playerId: string) {
  return queryOne(`
    SELECT
      SUM(pr.rec) as rec, SUM(pr.yds) as yds, SUM(pr.td) as td,
      COUNT(DISTINCT pr.game_id) as games,
      MIN(g.season) as first_season, MAX(g.season) as last_season
    FROM player_receiving pr
    JOIN games g ON pr.game_id = g.game_id
    WHERE pr.player_id = ?
  `, [playerId]);
}

export async function getPlayerSeasonStats(playerId: string) {
  return query(`
    SELECT g.season,
      SUM(pp.att) as pass_att, SUM(pp.com) as pass_com, SUM(pp.yds) as pass_yds,
      SUM(pp.td) as pass_td, SUM(pp.int_thrown) as pass_int,
      COUNT(DISTINCT pp.game_id) as pass_games
    FROM player_passing pp
    JOIN games g ON pp.game_id = g.game_id
    WHERE pp.player_id = ?
    GROUP BY g.season
    ORDER BY g.season
  `, [playerId]);
}

export async function getPlayerSeasonRushing(playerId: string) {
  return query(`
    SELECT g.season,
      SUM(pr.att) as rush_att, SUM(pr.yds) as rush_yds, SUM(pr.td) as rush_td,
      COUNT(DISTINCT pr.game_id) as rush_games
    FROM player_rushing pr
    JOIN games g ON pr.game_id = g.game_id
    WHERE pr.player_id = ?
    GROUP BY g.season
    ORDER BY g.season
  `, [playerId]);
}

export async function getPlayerSeasonReceiving(playerId: string) {
  return query(`
    SELECT g.season,
      SUM(pr.rec) as rec, SUM(pr.yds) as rec_yds, SUM(pr.td) as rec_td,
      COUNT(DISTINCT pr.game_id) as rec_games
    FROM player_receiving pr
    JOIN games g ON pr.game_id = g.game_id
    WHERE pr.player_id = ?
    GROUP BY g.season
    ORDER BY g.season
  `, [playerId]);
}

export async function getPlayerGameLog(playerId: string, season?: number) {
  const whereClause = season
    ? `AND g.season = ?`
    : ``;
  const args = season ? [playerId, playerId, playerId, season] : [playerId, playerId, playerId];

  return query(`
    SELECT g.game_id, g.season, g.game_date, g.opponent, g.home_away,
      g.saints_score, g.opponent_score, g.result, g.game_type,
      pp.att as pass_att, pp.com as pass_com, pp.yds as pass_yds,
      pp.td as pass_td, pp.int_thrown as pass_int, pp.rtg as pass_rtg,
      pr.att as rush_att, pr.yds as rush_yds, pr.td as rush_td,
      rec.rec, rec.yds as rec_yds, rec.td as rec_td
    FROM games g
    LEFT JOIN player_passing pp ON pp.game_id = g.game_id AND pp.player_id = ?
    LEFT JOIN player_rushing pr ON pr.game_id = g.game_id AND pr.player_id = ?
    LEFT JOIN player_receiving rec ON rec.game_id = g.game_id AND rec.player_id = ?
    WHERE (pp.player_id IS NOT NULL OR pr.player_id IS NOT NULL OR rec.player_id IS NOT NULL)
      AND g.game_type != 'preseason'
      ${whereClause}
    ORDER BY g.game_date DESC
  `, args);
}

// ── Player defensive stats ────────────────────────────

export async function getPlayerCareerDefense(playerId: string) {
  return queryOne(`
    SELECT
      COALESCE(def.tkl, 0) as tkl, COALESCE(def.tfl, 0) as tfl,
      COALESCE(def.qh, 0) as qh, COALESCE(def.pd_count, 0) as pd_count,
      COALESCE(def.ff, 0) as ff,
      COALESCE(sk.sacks, 0) as sacks,
      COALESCE(it.int_count, 0) as int_count,
      COALESCE(it.int_yds, 0) as int_yds,
      COALESCE(it.int_td, 0) as int_td,
      COALESCE(def.games, 0) + COALESCE(sk.games, 0) + COALESCE(it.games, 0) as games,
      MIN(COALESCE(def.first_season, sk.first_season, it.first_season)) as first_season,
      MAX(COALESCE(def.last_season, sk.last_season, it.last_season)) as last_season
    FROM (SELECT 1) dummy
    LEFT JOIN (
      SELECT SUM(pd.tkl) as tkl, SUM(pd.tfl) as tfl, SUM(pd.qh) as qh,
        SUM(pd.pd) as pd_count, SUM(pd.ff) as ff,
        COUNT(DISTINCT pd.game_id) as games,
        MIN(g.season) as first_season, MAX(g.season) as last_season
      FROM player_defense pd
      JOIN games g ON pd.game_id = g.game_id
      WHERE pd.player_id = ?
    ) def ON 1=1
    LEFT JOIN (
      SELECT SUM(ps.sacks) as sacks, COUNT(DISTINCT ps.game_id) as games,
        MIN(g.season) as first_season, MAX(g.season) as last_season
      FROM player_sacks ps
      JOIN games g ON ps.game_id = g.game_id
      WHERE ps.player_id = ?
    ) sk ON 1=1
    LEFT JOIN (
      SELECT SUM(pi.int_count) as int_count, SUM(pi.yds) as int_yds, SUM(pi.td) as int_td,
        COUNT(DISTINCT pi.game_id) as games,
        MIN(g.season) as first_season, MAX(g.season) as last_season
      FROM player_interceptions pi
      JOIN games g ON pi.game_id = g.game_id
      WHERE pi.player_id = ?
    ) it ON 1=1
  `, [playerId, playerId, playerId]);
}

export async function getPlayerSeasonDefense(playerId: string) {
  return query(`
    SELECT season,
      SUM(tkl) as tkl, SUM(tfl) as tfl, SUM(qh) as qh,
      SUM(pd_count) as pd_count, SUM(ff) as ff,
      SUM(sacks) as sacks, SUM(int_count) as int_count,
      MAX(games) as games
    FROM (
      SELECT g.season,
        SUM(pd.tkl) as tkl, SUM(pd.tfl) as tfl, SUM(pd.qh) as qh,
        SUM(pd.pd) as pd_count, SUM(pd.ff) as ff,
        0 as sacks, 0 as int_count,
        COUNT(DISTINCT pd.game_id) as games
      FROM player_defense pd
      JOIN games g ON pd.game_id = g.game_id
      WHERE pd.player_id = ?
      GROUP BY g.season

      UNION ALL

      SELECT g.season,
        0, 0, 0, 0, 0,
        SUM(ps.sacks) as sacks, 0,
        COUNT(DISTINCT ps.game_id) as games
      FROM player_sacks ps
      JOIN games g ON ps.game_id = g.game_id
      WHERE ps.player_id = ?
      GROUP BY g.season

      UNION ALL

      SELECT g.season,
        0, 0, 0, 0, 0,
        0, SUM(pi.int_count) as int_count,
        COUNT(DISTINCT pi.game_id) as games
      FROM player_interceptions pi
      JOIN games g ON pi.game_id = g.game_id
      WHERE pi.player_id = ?
      GROUP BY g.season
    ) combined
    GROUP BY season
    ORDER BY season
  `, [playerId, playerId, playerId]);
}

export async function getPlayerGamesPlayedByYear(playerId: string) {
  return query(`
    SELECT season, COUNT(DISTINCT game_id) as games
    FROM (
      SELECT g.season, pp.game_id FROM player_passing pp JOIN games g ON pp.game_id = g.game_id WHERE pp.player_id = ?
      UNION
      SELECT g.season, pr.game_id FROM player_rushing pr JOIN games g ON pr.game_id = g.game_id WHERE pr.player_id = ?
      UNION
      SELECT g.season, pr.game_id FROM player_receiving pr JOIN games g ON pr.game_id = g.game_id WHERE pr.player_id = ?
      UNION
      SELECT g.season, pd.game_id FROM player_defense pd JOIN games g ON pd.game_id = g.game_id WHERE pd.player_id = ?
      UNION
      SELECT g.season, ps.game_id FROM player_sacks ps JOIN games g ON ps.game_id = g.game_id WHERE ps.player_id = ?
      UNION
      SELECT g.season, pi.game_id FROM player_interceptions pi JOIN games g ON pi.game_id = g.game_id WHERE pi.player_id = ?
    ) all_games
    GROUP BY season
    ORDER BY season
  `, [playerId, playerId, playerId, playerId, playerId, playerId]);
}

// ── Leaderboards ───────────────────────────────────────

export async function getCareerPassingLeaders(limit = 25) {
  return query(`
    SELECT p.player_id, p.player_name,
      SUM(pp.yds) as yds, SUM(pp.td) as td, SUM(pp.int_thrown) as int_thrown,
      SUM(pp.com) as com, SUM(pp.att) as att,
      COUNT(DISTINCT pp.game_id) as games
    FROM player_passing pp
    JOIN players p ON pp.player_id = p.player_id
    JOIN games g ON pp.game_id = g.game_id
    WHERE g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    GROUP BY pp.player_id
    ORDER BY yds DESC
    LIMIT ?
  `, [limit]);
}

export async function getCareerRushingLeaders(limit = 25) {
  return query(`
    SELECT p.player_id, p.player_name,
      SUM(pr.yds) as yds, SUM(pr.td) as td, SUM(pr.att) as att,
      COUNT(DISTINCT pr.game_id) as games
    FROM player_rushing pr
    JOIN players p ON pr.player_id = p.player_id
    JOIN games g ON pr.game_id = g.game_id
    WHERE g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    GROUP BY pr.player_id
    ORDER BY yds DESC
    LIMIT ?
  `, [limit]);
}

export async function getCareerReceivingLeaders(limit = 25) {
  return query(`
    SELECT p.player_id, p.player_name,
      SUM(pr.yds) as yds, SUM(pr.td) as td, SUM(pr.rec) as rec,
      COUNT(DISTINCT pr.game_id) as games
    FROM player_receiving pr
    JOIN players p ON pr.player_id = p.player_id
    JOIN games g ON pr.game_id = g.game_id
    WHERE g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    GROUP BY pr.player_id
    ORDER BY yds DESC
    LIMIT ?
  `, [limit]);
}

export async function getSingleGamePassingLeaders(limit = 25) {
  return query(`
    SELECT p.player_id, p.player_name,
      pp.yds, pp.td, pp.com, pp.att, pp.int_thrown, pp.rtg,
      g.game_date, g.opponent, g.season
    FROM player_passing pp
    JOIN players p ON pp.player_id = p.player_id
    JOIN games g ON pp.game_id = g.game_id
    WHERE g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    ORDER BY pp.yds DESC
    LIMIT ?
  `, [limit]);
}

export async function getSingleGameRushingLeaders(limit = 25) {
  return query(`
    SELECT p.player_id, p.player_name,
      pr.yds, pr.td, pr.att,
      g.game_date, g.opponent, g.season
    FROM player_rushing pr
    JOIN players p ON pr.player_id = p.player_id
    JOIN games g ON pr.game_id = g.game_id
    WHERE g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    ORDER BY pr.yds DESC
    LIMIT ?
  `, [limit]);
}

export async function getSingleGameReceivingLeaders(limit = 25) {
  return query(`
    SELECT p.player_id, p.player_name,
      pr.yds, pr.td, pr.rec,
      g.game_date, g.opponent, g.season
    FROM player_receiving pr
    JOIN players p ON pr.player_id = p.player_id
    JOIN games g ON pr.game_id = g.game_id
    WHERE g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    ORDER BY pr.yds DESC
    LIMIT ?
  `, [limit]);
}

export async function getSeasonPassingRecords(limit = 25) {
  return query(`
    SELECT p.player_id, p.player_name, g.season,
      SUM(pp.yds) as yds, SUM(pp.td) as td, SUM(pp.int_thrown) as int_thrown,
      SUM(pp.com) as com, SUM(pp.att) as att,
      COUNT(DISTINCT pp.game_id) as games
    FROM player_passing pp
    JOIN players p ON pp.player_id = p.player_id
    JOIN games g ON pp.game_id = g.game_id
    WHERE g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    GROUP BY pp.player_id, g.season
    ORDER BY yds DESC
    LIMIT ?
  `, [limit]);
}

export async function getSeasonRushingRecords(limit = 25) {
  return query(`
    SELECT p.player_id, p.player_name, g.season,
      SUM(pr.yds) as yds, SUM(pr.td) as td, SUM(pr.att) as att,
      COUNT(DISTINCT pr.game_id) as games
    FROM player_rushing pr
    JOIN players p ON pr.player_id = p.player_id
    JOIN games g ON pr.game_id = g.game_id
    WHERE g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    GROUP BY pr.player_id, g.season
    ORDER BY yds DESC
    LIMIT ?
  `, [limit]);
}

export async function getSeasonReceivingRecords(limit = 25) {
  return query(`
    SELECT p.player_id, p.player_name, g.season,
      SUM(pr.yds) as yds, SUM(pr.td) as td, SUM(pr.rec) as rec,
      COUNT(DISTINCT pr.game_id) as games
    FROM player_receiving pr
    JOIN players p ON pr.player_id = p.player_id
    JOIN games g ON pr.game_id = g.game_id
    WHERE g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    GROUP BY pr.player_id, g.season
    ORDER BY yds DESC
    LIMIT ?
  `, [limit]);
}

// ── Defensive leaders ─────────────────────────────────
// Defense data spans three tables with different date ranges:
//   player_defense (tackles etc): 1999-present
//   player_sacks: 1973-present
//   player_interceptions: 1967-present
// We UNION all player IDs from all three tables so older legends appear.

export async function getCareerDefensiveLeaders(limit = 25) {
  return query(`
    SELECT p.player_id, p.player_name,
      COALESCE(def.tkl, 0) as tkl, COALESCE(def.tfl, 0) as tfl,
      COALESCE(def.qh, 0) as qh, COALESCE(def.pd_count, 0) as pd_count,
      COALESCE(def.ff, 0) as ff,
      COALESCE(sk.sacks, 0) as sacks,
      COALESCE(it.int_count, 0) as int_count,
      COALESCE(def.games, 0) + COALESCE(sk.games, 0) + COALESCE(it.games, 0) as games
    FROM (
      SELECT player_id FROM player_defense
      UNION
      SELECT player_id FROM player_sacks
      UNION
      SELECT player_id FROM player_interceptions
    ) all_def
    JOIN players p ON all_def.player_id = p.player_id
    LEFT JOIN (
      SELECT pd.player_id, SUM(pd.tkl) as tkl, SUM(pd.tfl) as tfl,
        SUM(pd.qh) as qh, SUM(pd.pd) as pd_count, SUM(pd.ff) as ff,
        COUNT(DISTINCT pd.game_id) as games
      FROM player_defense pd
      JOIN games g ON pd.game_id = g.game_id
      WHERE g.game_type = 'regular'
      GROUP BY pd.player_id
    ) def ON def.player_id = all_def.player_id
    LEFT JOIN (
      SELECT ps.player_id, SUM(ps.sacks) as sacks, COUNT(DISTINCT ps.game_id) as games
      FROM player_sacks ps
      JOIN games g ON ps.game_id = g.game_id
      WHERE g.game_type = 'regular'
      GROUP BY ps.player_id
    ) sk ON sk.player_id = all_def.player_id
    LEFT JOIN (
      SELECT pi.player_id, SUM(pi.int_count) as int_count, COUNT(DISTINCT pi.game_id) as games
      FROM player_interceptions pi
      JOIN games g ON pi.game_id = g.game_id
      WHERE g.game_type = 'regular'
      GROUP BY pi.player_id
    ) it ON it.player_id = all_def.player_id
    WHERE p.pfa_url IS NOT NULL
    ORDER BY sacks DESC
    LIMIT ?
  `, [limit]);
}

export async function getSeasonDefensiveRecords(limit = 25) {
  return query(`
    SELECT p.player_id, p.player_name, season,
      COALESCE(tkl, 0) as tkl, COALESCE(tfl, 0) as tfl,
      COALESCE(qh, 0) as qh, COALESCE(pd_count, 0) as pd_count,
      COALESCE(ff, 0) as ff,
      COALESCE(sacks, 0) as sacks,
      COALESCE(int_count, 0) as int_count,
      games
    FROM (
      SELECT pd.player_id, g.season,
        SUM(pd.tkl) as tkl, SUM(pd.tfl) as tfl, SUM(pd.qh) as qh,
        SUM(pd.pd) as pd_count, SUM(pd.ff) as ff,
        0 as sacks, 0 as int_count,
        COUNT(DISTINCT pd.game_id) as games
      FROM player_defense pd
      JOIN games g ON pd.game_id = g.game_id
      WHERE g.game_type = 'regular'
      GROUP BY pd.player_id, g.season

      UNION ALL

      SELECT ps.player_id, g.season,
        0 as tkl, 0 as tfl, 0 as qh, 0 as pd_count, 0 as ff,
        SUM(ps.sacks) as sacks, 0 as int_count,
        COUNT(DISTINCT ps.game_id) as games
      FROM player_sacks ps
      JOIN games g ON ps.game_id = g.game_id
      WHERE g.game_type = 'regular'
      GROUP BY ps.player_id, g.season

      UNION ALL

      SELECT pi.player_id, g.season,
        0 as tkl, 0 as tfl, 0 as qh, 0 as pd_count, 0 as ff,
        0 as sacks, SUM(pi.int_count) as int_count,
        COUNT(DISTINCT pi.game_id) as games
      FROM player_interceptions pi
      JOIN games g ON pi.game_id = g.game_id
      WHERE g.game_type = 'regular'
      GROUP BY pi.player_id, g.season
    ) combined
    JOIN players p ON combined.player_id = p.player_id
    WHERE p.pfa_url IS NOT NULL
    GROUP BY combined.player_id, season
    ORDER BY sacks DESC
    LIMIT ?
  `, [limit]);
}

export async function getSingleGameDefensiveLeaders(limit = 25) {
  return query(`
    SELECT p.player_id, p.player_name,
      COALESCE(pd.tkl, 0) as tkl, COALESCE(pd.tfl, 0) as tfl,
      COALESCE(pd.qh, 0) as qh, COALESCE(pd.pd, 0) as pd_count,
      COALESCE(pd.ff, 0) as ff,
      COALESCE(sk.sacks, 0) as sacks,
      COALESCE(it.int_count, 0) as int_count,
      g.game_date, g.opponent, g.season
    FROM (
      SELECT game_id, player_id FROM player_defense
      UNION
      SELECT game_id, player_id FROM player_sacks
      UNION
      SELECT game_id, player_id FROM player_interceptions
    ) all_gp
    JOIN players p ON all_gp.player_id = p.player_id
    JOIN games g ON all_gp.game_id = g.game_id
    LEFT JOIN player_defense pd ON pd.player_id = all_gp.player_id AND pd.game_id = all_gp.game_id
    LEFT JOIN player_sacks sk ON sk.player_id = all_gp.player_id AND sk.game_id = all_gp.game_id
    LEFT JOIN player_interceptions it ON it.player_id = all_gp.player_id AND it.game_id = all_gp.game_id
    WHERE g.game_type = 'regular'
      AND p.pfa_url IS NOT NULL
    ORDER BY sacks DESC, it.int_count DESC
    LIMIT ?
  `, [limit]);
}

// ── Recent games ───────────────────────────────────────

export async function getRecentGames(limit = 10): Promise<Game[]> {
  return query<Game>(
    `SELECT * FROM games WHERE game_type = 'regular' ORDER BY game_date DESC LIMIT ?`,
    [limit]
  );
}

// ── Draft ─────────────────────────────────────────────

export interface DraftPick {
  season: number;
  round: number;
  pick: number;
  player_name: string;
  player_id: string | null;
  position: string | null;
  college: string | null;
}

export interface DraftSummary {
  season: number;
  picks: number;
  first_pick: number;
  first_player: string;
}

export async function getDraftYears(): Promise<DraftSummary[]> {
  return query<DraftSummary>(`
    SELECT
      season,
      COUNT(*) as picks,
      MIN(pick) as first_pick,
      (SELECT player_name FROM draft_picks d2 WHERE d2.season = d.season ORDER BY pick LIMIT 1) as first_player
    FROM draft_picks d
    GROUP BY season
    ORDER BY season DESC
  `);
}

export async function getDraftByYear(year: number): Promise<(DraftPick & { linked_player_id: string | null })[]> {
  return query<DraftPick & { linked_player_id: string | null }>(`
    SELECT d.*,
      COALESCE(
        (SELECT p.player_id FROM players p WHERE p.player_id = d.player_id LIMIT 1),
        (SELECT p.player_id FROM players p WHERE LOWER(p.player_name) = LOWER(d.player_name) LIMIT 1)
      ) as linked_player_id
    FROM draft_picks d
    WHERE d.season = ?
    ORDER BY d.round, d.pick
  `, [year]);
}

export async function getRecentSeasons(limit = 3): Promise<SeasonSummary[]> {
  return query<SeasonSummary>(`
    SELECT
      season,
      SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) as wins,
      SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) as losses,
      SUM(CASE WHEN result = 'T' THEN 1 ELSE 0 END) as ties,
      COUNT(*) as games,
      COALESCE(SUM(saints_score), 0) as points_for,
      COALESCE(SUM(opponent_score), 0) as points_against
    FROM games
    WHERE game_type = 'regular'
    GROUP BY season
    ORDER BY season DESC
    LIMIT ?
  `, [limit]);
}
