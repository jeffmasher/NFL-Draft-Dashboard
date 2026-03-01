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

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const scope = searchParams.get("scope") ?? "career";
  const category = searchParams.get("category") ?? "passing";

  const fetchers: Record<string, Record<string, (limit?: number) => Promise<unknown[]>>> = {
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

  const data = await fetcher(50);
  return NextResponse.json(data);
}
