import re

with open('f:/ANHTHU/1-HCMUS/CONTEST/SEAHACKATHON/ai-service/frontend/app/components/live-studio.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update states and refs
content = re.sub(
    r'const \[commentIndex, setCommentIndex\] = useState\(4\);\n\s*const \[question, setQuestion\] = useState\(""\);\n\s*const \[pinnedAnswer, setPinnedAnswer\] = useState\([\s\S]*?\);\n\s*const videoRef = useRef<HTMLVideoElement>\(null\);',
    'const commentIndexRef = useRef(4);\n  const [question, setQuestion] = useState("");\n  const videoRef = useRef<HTMLVideoElement>(null);',
    content
)

# 2. Update timer logic
timer_old = '''    const timer = window.setInterval(() => {
      setCommentIndex((current) => {
        const nextRecord = initialComments[current % initialComments.length];
        const nextItem = toChatItem(nextRecord, current);
        setComments((items) => [...items.slice(-10), nextItem]);
        setPinnedAnswer(nextItem.answer ?? "");
        return current + 1;
      });
    }, 2600);'''
    
timer_new = '''    const timer = window.setInterval(() => {
      const current = commentIndexRef.current;
      const nextRecord = initialComments[current % initialComments.length];
      const nextItem = toChatItem(nextRecord, current);
      
      setComments((items) => [...items.slice(-10), nextItem]);
      commentIndexRef.current = current + 1;
    }, 2600);'''
content = content.replace(timer_old, timer_new)

# 3. Remove setPinnedAnswer from startLive, scheduleLive, generateVideo, submitQuestion
startLive_old = '''  function startLive() {
    setIsLive(true);
    setPinnedAnswer("Livestream đang phát, agent tự động đọc bình luận và phản hồi theo dữ liệu RAG.");
  }'''
startLive_new = '''  function startLive() {
    setIsLive(true);
  }'''
content = content.replace(startLive_old, startLive_new)

scheduleLive_old = '''  function scheduleLive() {
    setPinnedAnswer("Đã treo lịch live 20:30 hôm nay và đồng bộ kịch bản sang TikTok Shop.");
  }'''
scheduleLive_new = '''  function scheduleLive() {
  }'''
content = content.replace(scheduleLive_old, scheduleLive_new)

generateVideo_old = '''  function generateVideo() {
    setIsGenerating(true);
    setPinnedAnswer("Đang gen video highlight từ kịch bản live và câu hỏi có tín hiệu mua hàng cao.");
    window.setTimeout(() => {
      setIsGenerating(false);
      setPinnedAnswer("Video highlight đã sẵn sàng để tái dùng cho reels và short commerce.");
    }, 1800);
  }'''
generateVideo_new = '''  function generateVideo() {
    setIsGenerating(true);
    window.setTimeout(() => {
      setIsGenerating(false);
    }, 1800);
  }'''
content = content.replace(generateVideo_old, generateVideo_new)

submitQ_old = '''    setComments((items) => [...items.slice(-10), nextItem]);
    setPinnedAnswer(nextItem.answer ?? "");
    setQuestion("");'''
submitQ_new = '''    setComments((items) => [...items.slice(-10), nextItem]);
    setQuestion("");'''
content = content.replace(submitQ_old, submitQ_new)

# 4. Update the center section to be full screen
section_old = '''        <section className="flex min-h-[600px] min-w-0 flex-col items-center justify-center gap-4 overflow-hidden bg-gradient-to-b from-[#f5f2f5] to-[#fbfafc] px-3 py-5 md:min-h-[640px] md:px-4 lg:h-full lg:min-h-0">
          <div className="w-full max-w-[560px] rounded-[22px] border-[7px] border-[#24314a] bg-[#111a2c] p-4 shadow-live">
            <div className="relative aspect-[9/13] overflow-hidden rounded-xl bg-[#101827]">'''

section_new = '''        <section className="relative flex min-w-0 flex-col overflow-hidden bg-black lg:h-full">
          <div className="relative h-full w-full overflow-hidden">'''
content = content.replace(section_old, section_new)

video_old = '''                <video
                  ref={videoRef}
                  src="/api/live-video"
                  className={`h-full w-full object-cover transition-opacity duration-500 ${
                    isLive ? "opacity-100" : "opacity-18"
                  }`}
                  controls={isLive}
                  loop
                  muted={!isLive}
                  playsInline
                  preload="metadata"
                />
              ) : (
                <div className="h-full w-full bg-[#101827]" />
              )}'''

video_new = '''                <video
                  ref={videoRef}
                  src="/api/live-video"
                  className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-500 ${
                    isLive ? "opacity-100" : "opacity-18"
                  }`}
                  controls={isLive}
                  loop
                  muted={!isLive}
                  playsInline
                  preload="metadata"
                />
              ) : (
                <div className="absolute inset-0 bg-[#101827]" />
              )}'''
content = content.replace(video_old, video_new)

overlay_old = '''              {isLive ? (
                <LiveOverlay
                  answer={pinnedAnswer}
                  generating={isGenerating}
                  viewers={comments.length * 37 + 412}
                />
              ) : ('''

overlay_new = '''              {isLive ? (
                <LiveOverlay
                  topComment={hotLeads[0]}
                  generating={isGenerating}
                  viewers={comments.length * 37 + 412}
                />
              ) : ('''
content = content.replace(overlay_old, overlay_new)

end_section_old = '''            {actionModal.isOpen && (
              <ActionSelectVideoModal 
                assets={assets}
                onClose={() => setActionModal({ isOpen: false, actionType: null })}
                onSelect={(asset) => {
                  setSelectedVideo(asset);
                  setActionModal(prev => ({ ...prev, isOpen: false }));
                  
                  if (actionModal.actionType === "live") {
                    startLive();
                  } else if (actionModal.actionType === "schedule") {
                    scheduleLive();
                  } else if (actionModal.actionType === "generate") {
                    generateVideo();
                  }
                }}
              />
            )}
          </div>

          <button
            type="button"
            onClick={() => setIsLive((value) => !value)}
            className="grid size-16 place-items-center rounded-full bg-rose-500 text-white shadow-lg shadow-rose-300 transition hover:scale-105"
            aria-label={isLive ? "Tạm dừng live" : "Bật live"}
          >
            {isLive ? <RefreshCw size={28} /> : <Play size={28} fill="currentColor" />}
          </button>
        </section>'''

end_section_new = '''            {actionModal.isOpen && (
              <ActionSelectVideoModal 
                assets={assets}
                onClose={() => setActionModal({ isOpen: false, actionType: null })}
                onSelect={(asset) => {
                  setSelectedVideo(asset);
                  setActionModal(prev => ({ ...prev, isOpen: false }));
                  
                  if (actionModal.actionType === "live") {
                    startLive();
                  } else if (actionModal.actionType === "schedule") {
                    scheduleLive();
                  } else if (actionModal.actionType === "generate") {
                    generateVideo();
                  }
                }}
              />
            )}
            
            <button
              type="button"
              onClick={() => setIsLive((value) => !value)}
              className="absolute bottom-24 right-4 z-10 grid size-16 place-items-center rounded-full bg-rose-500 text-white shadow-lg shadow-rose-900/50 transition hover:scale-105"
              aria-label={isLive ? "Tạm dừng live" : "Bật live"}
            >
              {isLive ? <RefreshCw size={28} /> : <Play size={28} fill="currentColor" />}
            </button>
          </div>
        </section>'''
content = content.replace(end_section_old, end_section_new)

# 5. Remove Agent trả lời popup from sidebar
popup_old = '''            <div className="mt-3 shrink-0 rounded-lg border border-indigo-100 bg-indigo-50/70 p-3">
              <div className="mb-2 flex items-center gap-2 text-xs font-bold text-indigo-700">
                <Bot size={15} /> Agent trả lời
              </div>
              <p className="text-xs leading-5 text-slate-700">{pinnedAnswer}</p>
            </div>'''
content = content.replace(popup_old, '')

# 6. Update LiveOverlay
liveoverlay_old = '''function LiveOverlay({
  answer,
  generating,
  viewers,
}: {
  answer: string;
  generating: boolean;
  viewers: number;
}) {
  return (
    <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-4 text-white">
      <div className="flex items-start justify-between gap-3">
        <div className="rounded-full bg-rose-500 px-3 py-1.5 text-xs font-extrabold shadow-lg">
          LIVE
        </div>
        <div className="flex items-center gap-2 rounded-full bg-black/45 px-3 py-1.5 text-xs font-bold backdrop-blur">
          <Heart size={14} fill="currentColor" /> {viewers.toLocaleString("vi-VN")}
        </div>
      </div>

      <div className="mb-20 space-y-3">
        <div className="max-w-[86%] rounded-lg bg-black/48 p-3 backdrop-blur">
          <div className="mb-1 flex items-center gap-2 text-xs font-bold text-cyan-200">
            <Sparkles size={14} /> Agent đang trả lời
          </div>
          <p className="text-sm leading-5">{answer}</p>
        </div>'''

liveoverlay_new = '''function LiveOverlay({
  topComment,
  generating,
  viewers,
}: {
  topComment?: ChatItem;
  generating: boolean;
  viewers: number;
}) {
  return (
    <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-4 text-white">
      <div className="flex items-start justify-between gap-3">
        <div className="rounded-full bg-rose-500 px-3 py-1.5 text-xs font-extrabold shadow-lg">
          LIVE
        </div>
        <div className="flex items-center gap-2 rounded-full bg-black/45 px-3 py-1.5 text-xs font-bold backdrop-blur">
          <Heart size={14} fill="currentColor" /> {viewers.toLocaleString("vi-VN")}
        </div>
      </div>

      <div className="mb-20 space-y-3">
        {topComment && (
          <div className="max-w-[86%] rounded-lg bg-black/48 p-3 backdrop-blur border border-white/10">
            <div className="mb-1 flex items-center gap-2 text-xs font-bold text-amber-300">
              <Sparkles size={14} /> Top comment
            </div>
            <p className="text-sm font-semibold leading-5 text-white">{topComment.text}</p>
          </div>
        )}'''
content = content.replace(liveoverlay_old, liveoverlay_new)

# 7. Update CommentBubble
comment_old = '''function CommentBubble({ item }: { item: ChatItem }) {
  const badge =
    item.sentiment === "hot"
      ? "bg-rose-50 text-rose-600"
      : item.sentiment === "warm"
        ? "bg-amber-50 text-amber-600"
        : "bg-slate-100 text-slate-500";

  return (
    <article className="flex items-start gap-2">
      <div className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-100 text-[10px] font-bold text-emerald-700">
        {item.name
          .split(" ")
          .map((part) => part[0])
          .slice(-2)
          .join("")}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-1">
          <span className="text-xs font-bold text-slate-700">{item.name}</span>
          <BadgeCheck size={13} className="text-slate-900" />
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${badge}`}>
            {item.intent}
          </span>
        </div>
        <p className="rounded-lg bg-[#f1f5f9] px-3 py-2 text-sm leading-5 text-slate-800">
          {item.text}
        </p>
      </div>
    </article>
  );
}'''

comment_new = '''function CommentBubble({ item }: { item: ChatItem }) {
  const badge =
    item.sentiment === "hot"
      ? "bg-rose-50 text-rose-600"
      : item.sentiment === "warm"
        ? "bg-amber-50 text-amber-600"
        : "bg-slate-100 text-slate-500";

  return (
    <article className="flex flex-col gap-1">
      <div className="flex items-start gap-2">
        <div className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-100 text-[10px] font-bold text-emerald-700">
          {item.name
            .split(" ")
            .map((part) => part[0])
            .slice(-2)
            .join("")}
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-1">
            <span className="text-xs font-bold text-slate-700">{item.name}</span>
            <BadgeCheck size={13} className="text-slate-900" />
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${badge}`}>
              {item.intent}
            </span>
          </div>
          <p className="rounded-lg bg-[#f1f5f9] px-3 py-2 text-sm leading-5 text-slate-800">
            {item.text}
          </p>
        </div>
      </div>
      {item.answer && (
        <div className="ml-9 mt-1 flex items-start gap-2 rounded-lg border border-indigo-100 bg-indigo-50/70 px-3 py-2">
          <Bot size={15} className="mt-0.5 shrink-0 text-indigo-600" />
          <p className="text-xs leading-4 text-indigo-900">{item.answer}</p>
        </div>
      )}
    </article>
  );
}'''
content = content.replace(comment_old, comment_new)

with open('f:/ANHTHU/1-HCMUS/CONTEST/SEAHACKATHON/ai-service/frontend/app/components/live-studio.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
