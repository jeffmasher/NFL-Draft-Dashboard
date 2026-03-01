export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import {
  getCareerPassingLeaders,
  getCareerRushingLeaders,
  getCareerReceivingLeaders,
  getCareerDefensiveLeaders,
  getSeasonPassingRecords,
  getSeasonRushingRecords,
  getSeasonReceivingRecords,
  getSeasonDefensiveRecords,
  getSingleGamePassingLeaders,
  getSingleGameRushingLeaders,
  getSingleGameReceivingLeaders,
  getSingleGameDefensiveLeaders,
} from "@/lib/queries";

const VALID_GAME_TYPES = new Set(["regular", "playoff", "preseason"]);

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const scope = searchParams.get("scope") ?? "career";
  const category = searchParams.get("category") ?? "passing";
  const rawGameType = searchParams.get("gameType") ?? "regular";
  const gameType = VALID_GAME_TYPES.has(rawGameType) ? rawGameType : "regular";

  const fetchers: Record<string, Record<string, (limit?: number, gameType?: string) => Promise<unknown[]>>> = {
    career: {
      passing: getCareerPassingLeaders,
      rushing: getCareerRushingLeaders,
      receiving: getCareerReceivingLeaders,
      defense: getCareerDefensiveLeaders,
    },
    season: {
      passing: getSeasonPassingRecords,
      rushing: getSeasonRushingRecords,
      receiving: getSeasonReceivingRecords,
      defense: getSeasonDefensiveRecords,
    },
    game: {
      passing: getSingleGamePassingLeaders,
      rushing: getSingleGameRushingLeaders,
      receiving: getSingleGameReceivingLeaders,
      defense: getSingleGameDefensiveLeaders,
    },
  };

  const fetcher = fetchers[scope]?.[category];
  if (!fetcher) {
    return NextResponse.json({ error: "Invalid scope or category" }, { status: 400 });
  }

  const data = await fetcher(50, gameType);
  return NextResponse.json(data);
}
