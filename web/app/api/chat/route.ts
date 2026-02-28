import { streamText, stepCountIs, convertToModelMessages } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { saintsTools } from "@/lib/ai-tools";

export const maxDuration = 30;

export async function POST(req: Request) {
  const { messages } = await req.json();

  // Only send last 10 messages to reduce token cost
  const trimmedMessages = messages.slice(-10);

  const result = streamText({
    model: anthropic("claude-haiku-4-5-20251001"),
    system: `You are the Saints Encyclopedia AI assistant. You query a database and return data.

When answering questions:
- Use the available tools to query the database for accurate data
- The Saints won Super Bowl XLIV after the 2009 season, defeating the Colts 31-17

FORMATTING RULES:
- For multi-row results, ALWAYS use a markdown table. Never use bulleted lists or numbered lists for stats.
- Use short column headers: Player, Season, GP, Yds, TD, etc.
- Add commas to numbers over 999 (e.g. 5,208).
- One short intro sentence before the table is fine. Do NOT add commentary, analysis, takeaways, or narrative after the table. Just the data.
- For single facts, answer in one sentence. No elaboration.`,
    messages: await convertToModelMessages(trimmedMessages),
    tools: saintsTools,
    maxOutputTokens: 1024,
    stopWhen: stepCountIs(3),
  });

  return result.toUIMessageStreamResponse();
}
