import re

file_path = 'f:/ANHTHU/1-HCMUS/CONTEST/SEAHACKATHON/ai-service/frontend/app/components/live-studio.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add states and scroll handler
ref_old = '''  const videoRef = useRef<HTMLVideoElement>(null);
  const commentsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (commentsEndRef.current) {
      commentsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [comments]);'''

ref_new = '''  const videoRef = useRef<HTMLVideoElement>(null);
  const commentsEndRef = useRef<HTMLDivElement>(null);
  const commentsContainerRef = useRef<HTMLDivElement>(null);
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const [isWebcamActive, setIsWebcamActive] = useState(false);

  const handleScroll = () => {
    if (commentsContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = commentsContainerRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 10;
      setIsAutoScroll(isAtBottom);
    }
  };

  useEffect(() => {
    if (isAutoScroll && commentsEndRef.current) {
      commentsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [comments, isAutoScroll]);
  
  function startWebcamLive() {
    setIsWebcamActive(true);
    setIsLive(true);
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      navigator.mediaDevices.getUserMedia({ video: true }).then((stream) => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      }).catch(err => {
        console.error("Camera access denied", err);
      });
    }
  }'''
content = content.replace(ref_old, ref_new)

# 2. Update comments container wrapper to attach ref and onScroll
comments_old = '''            <div
              className="h-44 min-h-0 shrink-0 space-y-3 overflow-y-auto overscroll-contain pr-1 lg:h-48"
            >'''
comments_new = '''            <div
              ref={commentsContainerRef}
              onScroll={handleScroll}
              className="h-44 min-h-0 shrink-0 space-y-3 overflow-y-auto overscroll-contain pr-1 lg:h-48"
            >'''
content = content.replace(comments_old, comments_new)

# 3. Update video tag
video_old = '''              {selectedVideo ? (
                <video
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
              ) : ('''
video_new = '''              {selectedVideo || isWebcamActive ? (
                <video
                  ref={videoRef}
                  src={isWebcamActive ? undefined : "/api/live-video"}
                  className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-500 ${
                    isLive ? "opacity-100" : "opacity-18"
                  } ${isWebcamActive ? "contrast-125 brightness-110 saturate-[1.2] sepia-[.15]" : ""}`}
                  controls={isLive && !isWebcamActive}
                  loop={!isWebcamActive}
                  muted={!isLive}
                  playsInline
                  autoPlay={isWebcamActive}
                  preload="metadata"
                />
              ) : ('''
content = content.replace(video_old, video_new)

# 4. Update LiveOverlay usage to pass isWebcamActive
overlay_old = '''                <LiveOverlay
                  topComment={hotLeads[0]}
                  generating={isGenerating}
                  viewers={comments.length * 37 + 412}
                />'''
overlay_new = '''                <LiveOverlay
                  topComment={hotLeads[0]}
                  generating={isGenerating}
                  viewers={comments.length * 37 + 412}
                  isWebcamActive={isWebcamActive}
                />'''
content = content.replace(overlay_old, overlay_new)

# 5. Update LiveOverlay definition to accept isWebcamActive
lo_def_old = '''function LiveOverlay({
  topComment,
  generating,
  viewers,
}: {
  topComment?: ChatItem;
  generating: boolean;
  viewers: number;
}) {'''
lo_def_new = '''function LiveOverlay({
  topComment,
  generating,
  viewers,
  isWebcamActive,
}: {
  topComment?: ChatItem;
  generating: boolean;
  viewers: number;
  isWebcamActive?: boolean;
}) {'''
content = content.replace(lo_def_old, lo_def_new)

# 6. Add Deepface Active badge in LiveOverlay
lo_badge_old = '''        <div className="flex items-center gap-2 rounded-full bg-black/45 px-3 py-1.5 text-xs font-bold backdrop-blur">
          <Heart size={14} fill="currentColor" /> {viewers.toLocaleString("vi-VN")}
        </div>
      </div>'''
lo_badge_new = '''        <div className="flex items-center gap-2 rounded-full bg-black/45 px-3 py-1.5 text-xs font-bold backdrop-blur">
          <Heart size={14} fill="currentColor" /> {viewers.toLocaleString("vi-VN")}
        </div>
      </div>
      {isWebcamActive && (
        <div className="absolute top-14 left-4 rounded-full border border-pink-500/30 bg-pink-500/20 px-2 py-1 text-[10px] font-bold text-pink-300 backdrop-blur flex items-center gap-1">
          <Sparkles size={10} /> Deepface Filter
        </div>
      )}'''
content = content.replace(lo_badge_old, lo_badge_new)

# 7. Update ReadyState
rs_old = '''                <ReadyState
                  onStart={() => setActionModal({ isOpen: true, actionType: "live" })}
                  onSchedule={() => setActionModal({ isOpen: true, actionType: "schedule" })}
                  onGenerate={() => setActionModal({ isOpen: true, actionType: "generate" })}
                />'''
rs_new = '''                <ReadyState
                  onStart={startWebcamLive}
                  onSchedule={() => setActionModal({ isOpen: true, actionType: "schedule" })}
                  onGenerate={() => setIsAddVideoModalOpen(true)}
                />'''
content = content.replace(rs_old, rs_new)

# 8. Update toggle live button to stop webcam properly
btn_old = '''            <button
              type="button"
              onClick={() => setIsLive((value) => !value)}
              className="absolute bottom-24 right-4 z-10 grid size-16 place-items-center rounded-full bg-rose-500 text-white shadow-lg shadow-rose-900/50 transition hover:scale-105"
              aria-label={isLive ? "Tạm dừng live" : "Bật live"}
            >'''
btn_new = '''            <button
              type="button"
              onClick={() => {
                setIsLive((value) => !value);
                if (isWebcamActive && isLive) {
                  setIsWebcamActive(false);
                  if (videoRef.current && videoRef.current.srcObject) {
                    const stream = videoRef.current.srcObject as MediaStream;
                    stream.getTracks().forEach(track => track.stop());
                    videoRef.current.srcObject = null;
                  }
                }
              }}
              className="absolute bottom-24 right-4 z-10 grid size-16 place-items-center rounded-full bg-rose-500 text-white shadow-lg shadow-rose-900/50 transition hover:scale-105"
              aria-label={isLive ? "Tạm dừng live" : "Bật live"}
            >'''
content = content.replace(btn_old, btn_new)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
