import { createReadStream, statSync } from "fs";
import { join } from "path";
import { Readable } from "stream";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const videoPath = join(
  process.cwd(),
  "..",
  "data",
  "final_video_mechanical_all_audio.mp4",
);

export async function GET(request: Request) {
  const stat = statSync(videoPath);
  const range = request.headers.get("range");

  if (!range) {
    const stream = createReadStream(videoPath);
    return new Response(Readable.toWeb(stream) as ReadableStream, {
      headers: {
        "Content-Length": String(stat.size),
        "Content-Type": "video/mp4",
      },
    });
  }

  const chunkSize = 1024 * 1024;
  const match = range.match(/bytes=(\d+)-(\d*)/);
  const start = match ? Number(match[1]) : 0;
  const requestedEnd = match?.[2] ? Number(match[2]) : start + chunkSize - 1;
  const end = Math.min(requestedEnd, stat.size - 1);
  const contentLength = end - start + 1;
  const stream = createReadStream(videoPath, { start, end });

  return new Response(Readable.toWeb(stream) as ReadableStream, {
    status: 206,
    headers: {
      "Accept-Ranges": "bytes",
      "Content-Length": String(contentLength),
      "Content-Range": `bytes ${start}-${end}/${stat.size}`,
      "Content-Type": "video/mp4",
    },
  });
}

export async function HEAD() {
  const stat = statSync(videoPath);

  return new Response(null, {
    headers: {
      "Accept-Ranges": "bytes",
      "Content-Length": String(stat.size),
      "Content-Type": "video/mp4",
    },
  });
}
