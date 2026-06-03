import re

file_path = 'f:/ANHTHU/1-HCMUS/CONTEST/SEAHACKATHON/ai-service/frontend/app/components/live-studio.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add commentsEndRef and useEffect
ref_old = '  const videoRef = useRef<HTMLVideoElement>(null);'
ref_new = '''  const videoRef = useRef<HTMLVideoElement>(null);
  const commentsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (commentsEndRef.current) {
      commentsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [comments]);'''
content = content.replace(ref_old, ref_new)

# 2. Add dummy div to comments container
comments_old = '''            <div
              className="h-44 min-h-0 shrink-0 space-y-3 overflow-y-auto overscroll-contain pr-1 lg:h-48"
            >
              {comments.map((item) => (
                <CommentBubble key={item.id} item={item} />
              ))}
            </div>'''
comments_new = '''            <div
              className="h-44 min-h-0 shrink-0 space-y-3 overflow-y-auto overscroll-contain pr-1 lg:h-48"
            >
              {comments.map((item) => (
                <CommentBubble key={item.id} item={item} />
              ))}
              <div ref={commentsEndRef} />
            </div>'''
content = content.replace(comments_old, comments_new)

# 3. Add scroll to Kho nội dung
sidebar_old = '''          <section className="mt-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                Kho nội dung
              </h2>
              <Settings2 size={16} className="text-slate-400" />
            </div>
            <div className="space-y-3">'''
sidebar_new = '''          <section className="mt-5 flex min-h-0 flex-1 flex-col">
            <div className="mb-3 flex shrink-0 items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                Kho nội dung
              </h2>
              <Settings2 size={16} className="text-slate-400" />
            </div>
            <div className="space-y-3 overflow-y-auto pb-4 pr-1">'''
content = content.replace(sidebar_old, sidebar_new)

# 4. Change center video to 9:16 aspect ratio
video_old = '''        <section className="relative flex min-w-0 flex-col overflow-hidden bg-black lg:h-full">
          <div className="relative h-full w-full overflow-hidden">'''
video_new = '''        <section className="relative flex min-w-0 flex-col items-center justify-center overflow-hidden bg-black lg:h-full">
          <div className="relative h-full aspect-[9/16] overflow-hidden bg-[#101827] shadow-2xl">'''
content = content.replace(video_old, video_new)


with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
