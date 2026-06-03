import { readFile } from "fs/promises";
import { join } from "path";
import { LiveStudio, type CommentRecord } from "./components/live-studio";

async function getComments(): Promise<CommentRecord[]> {
  const filePath = join(
    process.cwd(),
    "..",
    "dang_rag",
    "database",
    "comments.json",
  );
  const raw = await readFile(filePath, "utf8");
  return JSON.parse(raw) as CommentRecord[];
}

export default async function Home() {
  const comments = await getComments();

  return <LiveStudio initialComments={comments} />;
}
