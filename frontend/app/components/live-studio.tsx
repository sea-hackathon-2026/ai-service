"use client";

import {
  Activity,
  BadgeCheck,
  BarChart3,
  Bot,
  CalendarClock,
  ChevronRight,
  CircleDollarSign,
  Clapperboard,
  Clock3,
  Gift,
  Heart,
  Link2,
  MessageCircle,
  Mic2,
  Package,
  Play,
  Plus,
  Radio,
  RefreshCw,
  Send,
  Settings2,
  ShoppingBag,
  Sparkles,
  Video,
  Wand2,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

export type CommentRecord = {
  timestamp: string;
  comment: string;
};

type ChatItem = {
  id: number;
  name: string;
  text: string;
  intent: string;
  answer?: string;
  sentiment: "hot" | "warm" | "neutral";
};

const shoppers = [
  "Hoàng Nam",
  "Minh Thư",
  "Lê Tuyết",
  "Bảo Anh",
  "Thanh Vy",
  "Gia Hân",
  "Quốc Bảo",
  "Mai Linh",
];

const product = {
  name: "Gel tẩy da chết cà phê Đắk Lắk",
  price: "125.000đ",
  promo: "Mua 2 giảm thêm 12%",
};

const manualQuestions = [
  "Sản phẩm này dùng cho da nhạy cảm được không?",
  "Shop có ship Hà Nội không ạ?",
  "Mua 2 hũ có giảm thêm không?",
];

function detectIntent(text: string) {
  const lower = text.toLowerCase();

  if (/(giá|bao nhiêu|mua 2|giảm|combo|mã)/i.test(lower)) {
    return "Giá & ưu đãi";
  }

  if (/(ship|hà nội|miền bắc|sài gòn|order|đặt hàng)/i.test(lower)) {
    return "Vận chuyển";
  }

  if (/(da|bầu|trẻ em|an toàn|mặt|gluten|dùng được)/i.test(lower)) {
    return "Tư vấn sản phẩm";
  }

  if (/(hàng|chính hãng|hạn sử dụng|có hàng|hết hàng)/i.test(lower)) {
    return "Tồn kho";
  }

  return "Tương tác";
}

function buildAnswer(text: string) {
  const lower = text.toLowerCase();

  if (/(giá|bao nhiêu)/i.test(lower)) {
    return `${product.name} đang có giá ${product.price}. Trong live này khách chốt đơn được áp mã freeship và quà mini size.`;
  }

  if (/(mua 2|combo|giảm|mã)/i.test(lower)) {
    return `Có nha, ${product.promo}. Agent đã ghim ưu đãi ở giỏ hàng để khách chốt ngay trong live.`;
  }

  if (/(ship|hà nội|miền bắc|sài gòn|order|đặt hàng)/i.test(lower)) {
    return "Shop giao toàn quốc. Nội thành thường 1-2 ngày, miền Bắc khoảng 2-4 ngày, có COD và theo dõi vận đơn.";
  }

  if (/(da nhạy cảm|nhạy cảm|mặt|an toàn|bầu|trẻ em|gluten|dùng được)/i.test(lower)) {
    return "Sản phẩm hạt mịn, ưu tiên massage nhẹ 1-2 lần mỗi tuần. Da nhạy cảm nên test vùng nhỏ trước khi dùng toàn mặt.";
  }

  if (/(hàng|chính hãng|hạn sử dụng|có hàng|hết hàng)/i.test(lower)) {
    return "Hàng chính hãng, lô mới còn hạn dài. Hiện còn sẵn hàng trong kho live, agent có thể giữ đơn ngay.";
  }

  return "Cảm ơn bạn đã tương tác. Agent đã ghi nhận câu hỏi và sẽ ưu tiên nhắc lại ưu đãi phù hợp trong live.";
}

function toChatItem(record: CommentRecord, index: number): ChatItem {
  const intent = detectIntent(record.comment);
  const hasBuyingSignal = /giá|mua|ship|order|đặt|giảm|combo|có hàng/i.test(
    record.comment,
  );

  return {
    id: index,
    name: shoppers[index % shoppers.length],
    text: record.comment,
    intent,
    answer: buildAnswer(record.comment),
    sentiment: hasBuyingSignal ? "hot" : intent === "Tương tác" ? "neutral" : "warm",
  };
}

type Asset = {
  id: number;
  title: string;
  duration: string;
  icon: string;
  active?: boolean;
  muted?: boolean;
  bars?: boolean;
  isCreating?: boolean;
};

export function LiveStudio({
  initialComments,
}: {
  initialComments: CommentRecord[];
}) {
  const [isLive, setIsLive] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [assets, setAssets] = useState<Asset[]>([
    { id: 1, title: "LIVE LOOP", duration: "15s", icon: "Radio", active: true, bars: true },
    { id: 2, title: "45s", duration: "Q&A cut", icon: "BarChart3", bars: true },
    { id: 3, title: "01:20", duration: "Waiting room", icon: "Clapperboard", muted: true },
  ]);
  const [isAddVideoModalOpen, setIsAddVideoModalOpen] = useState(false);
  const [actionModal, setActionModal] = useState<{ isOpen: boolean; actionType: "live" | "schedule" | "generate" | null }>({ isOpen: false, actionType: null });
  const [selectedVideo, setSelectedVideo] = useState<any | null>(null);

  const [comments, setComments] = useState<ChatItem[]>(() =>
    initialComments.slice(0, 4).map(toChatItem),
  );
  const commentIndexRef = useRef(4);
  const [question, setQuestion] = useState("");
  const videoRef = useRef<HTMLVideoElement>(null);
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
  }
  const chatListRef = useRef<HTMLDivElement>(null);

  const hotLeads = useMemo(
    () => comments.filter((item) => item.sentiment === "hot").slice(-3).reverse(),
    [comments],
  );

  useEffect(() => {
    if (!isLive || initialComments.length === 0) {
      return;
    }

    const timer = window.setInterval(() => {
      const current = commentIndexRef.current;
      const nextRecord = initialComments[current % initialComments.length];
      const nextItem = toChatItem(nextRecord, current);
      
      setComments((items) => [...items.slice(-10), nextItem]);
      commentIndexRef.current = current + 1;
    }, 2600);

    return () => window.clearInterval(timer);
  }, [initialComments, isLive]);

  useEffect(() => {
    if (isLive) {
      void videoRef.current?.play();
    } else {
      videoRef.current?.pause();
    }
  }, [isLive]);

  useEffect(() => {
    const chatList = chatListRef.current;

    if (chatList) {
      chatList.scrollTop = chatList.scrollHeight;
    }
  }, [comments.length]);

  function startLive() {
    setIsLive(true);
  }

  function scheduleLive() {
    setIsLive(true);
    setTimeout(() => {
      if (videoRef.current) {
        videoRef.current.play().catch(console.error);
      }
    }, 100);
  }

  function generateVideo() {
    setIsGenerating(true);
    window.setTimeout(() => {
      setIsGenerating(false);
    }, 1800);
  }

  function submitQuestion(text = question) {
    const trimmed = text.trim();

    if (!trimmed) {
      return;
    }

    const nextItem: ChatItem = {
      id: Date.now(),
      name: "Khách mới",
      text: trimmed,
      intent: detectIntent(trimmed),
      answer: buildAnswer(trimmed),
      sentiment: /giá|mua|ship|order|đặt|giảm|combo|có hàng/i.test(trimmed)
        ? "hot"
        : "warm",
    };

    setComments((items) => [...items.slice(-10), nextItem]);
    setQuestion("");
  }

  return (
    <main className="min-h-screen w-screen max-w-[100vw] overflow-x-hidden text-ink lg:h-screen lg:overflow-hidden bg-[#fbf7fb]">
      <div className="grid min-h-screen w-full max-w-full min-w-0 grid-cols-[minmax(0,1fr)] overflow-hidden shadow-live lg:min-h-0 lg:h-full lg:grid-cols-[280px_minmax(460px,1fr)_360px]">
        <aside className="flex min-h-0 min-w-0 flex-col border-b border-slate-200 bg-[#fbf9fb] p-3 md:p-4 lg:h-full lg:overflow-hidden lg:border-b-0 lg:border-r">
          <section className="rounded-lg bg-[#101a30] p-4 text-white shadow-lg">
            <div className="flex items-center gap-3">
              <div className="grid size-11 place-items-center rounded-md bg-violetLive">
                <Zap size={22} fill="currentColor" />
              </div>
              <div>
                <h1 className="text-sm font-bold">Campaign Hè 2024</h1>
                <p className="text-[11px] text-sky-200">ContentOps AI</p>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 divide-x divide-slate-700 border-t border-slate-700 pt-3 text-center">
              <div>
                <p className="text-[11px] text-slate-400">Sản phẩm</p>
                <p className="text-lg font-bold">12</p>
              </div>
              <div>
                <p className="text-[11px] text-slate-400">Videos</p>
                <p className="text-lg font-bold">8</p>
              </div>
            </div>
          </section>

          <section className="mt-5 flex min-h-0 flex-1 flex-col">
            <div className="mb-3 flex shrink-0 items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                Kho nội dung
              </h2>
              <Settings2 size={16} className="text-slate-400" />
            </div>
            <div className="flex-1 min-h-0 space-y-3 overflow-y-auto pb-4 pr-1">
              {assets.map((asset) => (
                <AssetCard
                  key={asset.id}
                  active={asset.active}
                  title={asset.title}
                  duration={asset.duration}
                  iconName={asset.icon}
                  bars={asset.bars}
                  muted={asset.muted}
                  isCreating={asset.isCreating}
                />
              ))}
            </div>
          </section>

          <div className="mt-auto hidden space-y-2 pt-6 lg:block">
            <button
              type="button"
              onClick={() => setIsAddVideoModalOpen(true)}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-md border border-slate-200 bg-white text-sm font-semibold text-slate-700"
            >
              <Plus size={16} /> Video
            </button>
            <button
              type="button"
              className="flex h-12 w-full items-center justify-center gap-2 rounded-md bg-violetLive text-sm font-bold text-white"
            >
              <BarChart3 size={16} /> Dashboard
            </button>
          </div>
        </aside>

        <section className="relative flex min-w-0 flex-col items-center justify-center overflow-hidden bg-black lg:h-full">
          <div className="relative h-full aspect-[9/16] overflow-hidden bg-[#101827] shadow-2xl">
              {selectedVideo || isWebcamActive ? (
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
              ) : (
                <div className="absolute inset-0 bg-[#101827]" />
              )}

              <div className="pointer-events-none absolute inset-0 scanline" />

              {isLive ? (
                <LiveOverlay
                  topComment={hotLeads[0]}
                  generating={isGenerating}
                  viewers={comments.length * 37 + 412}
                  isWebcamActive={isWebcamActive}
                />
              ) : (
                <ReadyState
                  onStart={startWebcamLive}
                  onSchedule={() => setActionModal({ isOpen: true, actionType: "schedule" })}
                  onGenerate={() => setIsAddVideoModalOpen(true)}
                />
              )}

              <ProductDock />
            </div>
            
            {isAddVideoModalOpen && (
              <AddVideoModal 
                onClose={() => setIsAddVideoModalOpen(false)}
                onSubmit={(data) => {
                  setAssets((prev) => [...prev, {
                    id: Date.now(),
                    title: "Video mới",
                    duration: "Đang tạo...",
                    icon: "Video",
                    muted: true,
                    isCreating: true
                  }]);
                  setIsAddVideoModalOpen(false);
                }}
              />
            )}
            
            {actionModal.isOpen && (
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
              onClick={() => {
                setIsLive((value) => {
                  const nextValue = !value;
                  if (!isWebcamActive && videoRef.current) {
                    if (nextValue) {
                      videoRef.current.play().catch(console.error);
                    } else {
                      videoRef.current.pause();
                    }
                  }
                  return nextValue;
                });
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
            >
              {isLive ? <RefreshCw size={28} /> : <Play size={28} fill="currentColor" />}
            </button>
        </section>

        <aside className="flex min-h-0 min-w-0 flex-col border-t border-slate-200 bg-[#fbf9fb] p-3 md:p-4 lg:h-full lg:overflow-y-auto lg:border-l lg:border-t-0">
          <section>
            <h2 className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
              Kênh đang kết nối
            </h2>
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3 lg:grid-cols-3">
              <ChannelBadge label="TikTok" status="+1.2K" active />
              <ChannelBadge label="Facebook" status="Offline" />
              <ChannelBadge label="Shopee" status="Offline" accent="orange" />
            </div>
          </section>



          <section className="mt-4 flex min-h-0 flex-1 flex-col overflow-visible lg:overflow-hidden">
            <div className="mb-3 flex items-center justify-between shrink-0">
              <h2 className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                Bình luận trực tiếp
              </h2>
              <span className="flex items-center gap-1 text-[11px] font-bold text-emerald-600">
                <span className="size-2 rounded-full bg-emerald-500" /> AI online
              </span>
            </div>

            <div
              data-testid="live-chat-list"
              ref={chatListRef}
              className="h-44 min-h-0 shrink-0 space-y-3 overflow-y-auto overscroll-contain pr-1 lg:h-48"
            >
              {comments.map((item) => (
                <CommentBubble key={item.id} item={item} />
              ))}
            </div>



            <div className="mt-3 flex shrink-0 gap-2 overflow-x-auto pb-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              {manualQuestions.map((item) => (
                <button
                  type="button"
                  key={item}
                  onClick={() => submitQuestion(item)}
                  className="shrink-0 whitespace-nowrap rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-600 transition hover:border-violetLive hover:text-violetLive"
                >
                  {item}
                </button>
              ))}
            </div>

            <form
              className="mt-3 shrink-0 flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                submitQuestion();
              }}
            >
              <input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Nhập câu hỏi của khách..."
                className="h-11 min-w-0 flex-1 rounded-md border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-violetLive"
              />
              <button
                type="submit"
                className="grid size-11 place-items-center rounded-md bg-ink text-white"
                aria-label="Gửi câu hỏi"
              >
                <Send size={17} />
              </button>
            </form>
          </section>

          <section className="mt-4 shrink-0 flex flex-col min-h-0 rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between shrink-0">
              <h2 className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                Hot leads
              </h2>
              <span className="text-[11px] font-bold text-violetLive">Top 3</span>
            </div>
            <div className="space-y-2 overflow-y-auto max-h-[240px] pr-1">
              {hotLeads.map((lead, index) => (
                <div
                  key={`${lead.id}-lead`}
                  className="flex items-center gap-3 rounded-md border border-slate-100 bg-slate-50 p-2"
                >
                  <div className="grid size-8 place-items-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-500">
                    {lead.name
                      .split(" ")
                      .map((part) => part[0])
                      .slice(-2)
                      .join("")}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-bold text-ink">{lead.name}</p>
                    <p className="truncate text-[11px] text-rose-500">{lead.intent}</p>
                  </div>
                  <button
                    type="button"
                    className="rounded-full bg-ink px-3 py-1.5 text-[11px] font-bold text-white"
                  >
                    Liên hệ
                  </button>
                </div>
              ))}
              {hotLeads.length === 0 ? (
                <p className="rounded-md bg-slate-50 p-3 text-xs text-slate-500">
                  Chưa có lead nóng.
                </p>
              ) : null}
            </div>
          </section>
        </aside>
      </div>
    </main>
  );
}

function AssetCard({
  title,
  duration,
  iconName,
  active = false,
  muted = false,
  bars = false,
  isCreating = false,
}: {
  title: string;
  duration: string;
  iconName: string;
  active?: boolean;
  muted?: boolean;
  bars?: boolean;
  isCreating?: boolean;
}) {
  const getIcon = () => {
    switch (iconName) {
      case "Radio": return <Radio size={18} />;
      case "BarChart3": return <BarChart3 size={18} />;
      case "Clapperboard": return <Clapperboard size={18} />;
      default: return <Video size={18} />;
    }
  };

  return (
    <button
      type="button"
      className={`relative h-28 w-full overflow-hidden rounded-md text-left ${
        muted
          ? "bg-slate-200"
          : "bg-[#101827] shadow-md shadow-slate-200"
      }`}
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_78%_35%,rgba(139,92,246,0.42),transparent_30%),linear-gradient(135deg,rgba(15,23,42,0.95),rgba(30,41,59,0.72))]" />
      {bars ? (
        <div className="absolute inset-x-5 bottom-8 flex h-12 items-end gap-2">
          {[38, 58, 42, 70, 52, 46, 62, 35].map((height, index) => (
            <span
              key={index}
              className="flex-1 rounded-sm bg-cyan-300/70"
              style={{ height: `${height}%` }}
            />
          ))}
        </div>
      ) : null}
      <div className="absolute inset-0 grid place-items-center text-slate-400">
        {getIcon()}
      </div>
      <div className="absolute bottom-2 left-2 flex items-center gap-1 text-[10px] font-bold text-white">
        {active ? (
          <span className="rounded-sm bg-violetLive px-1.5 py-0.5">LIVE LOOP</span>
        ) : null}
        <span>{active ? duration : title}</span>
        {isCreating && <span className="ml-2 rounded-sm bg-amber-500 px-1.5 py-0.5 text-white">Đang tạo</span>}
      </div>
    </button>
  );
}

function ReadyState({
  onStart,
  onSchedule,
  onGenerate,
}: {
  onStart: () => void;
  onSchedule: () => void;
  onGenerate: () => void;
}) {
  return (
    <div className="absolute inset-0 grid place-items-center bg-[#101827]/78 px-7 text-center text-white">
      <div className="w-full max-w-64">
        <div className="mx-auto grid size-24 place-items-center rounded-full border border-white/15 bg-white/10 text-white">
          <Video size={39} />
        </div>
        <h2 className="mt-6 text-2xl font-extrabold">Sẵn sàng phát</h2>
        <p className="mt-1 text-sm text-sky-100">Agent và video live đã được nạp</p>
        <div className="mt-7 space-y-3">
          <button
            type="button"
            onClick={onStart}
            className="h-14 w-full rounded-full bg-violetLive text-sm font-bold text-white shadow-lg shadow-violet-900/30"
          >
            LIVE NGAY
          </button>
          <button
            type="button"
            onClick={onSchedule}
            className="h-14 w-full rounded-full bg-slate-700/80 text-sm font-bold text-slate-200"
          >
            TREO LIVE
          </button>
          <button
            type="button"
            onClick={onGenerate}
            className="h-12 w-full text-sm font-bold text-sky-100"
          >
            TẠO VIDEO
          </button>
        </div>
      </div>
    </div>
  );
}

function LiveOverlay({
  topComment,
  generating,
  viewers,
  isWebcamActive,
}: {
  topComment?: ChatItem;
  generating: boolean;
  viewers: number;
  isWebcamActive?: boolean;
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
      {isWebcamActive && (
        <div className="absolute top-14 left-4 rounded-full border border-pink-500/30 bg-pink-500/20 px-2 py-1 text-[10px] font-bold text-pink-300 backdrop-blur flex items-center gap-1">
          <Sparkles size={10} /> Deepface Filter
        </div>
      )}

      <div className="mb-20 space-y-3">
        {topComment && (
          <div className="max-w-[86%] rounded-lg bg-black/48 p-3 backdrop-blur border border-white/10">
            <div className="mb-1 flex items-center gap-2 text-xs font-bold text-amber-300">
              <Sparkles size={14} /> Top comment
            </div>
            <p className="text-sm font-semibold leading-5 text-white">{topComment.text}</p>
          </div>
        )}
        <div className="flex items-center gap-2 text-xs font-bold">
          {generating ? (
            <span className="flex items-center gap-2 rounded-full bg-violetLive px-3 py-1.5">
              <Wand2 size={14} /> Gen video
            </span>
          ) : (
            <span className="flex items-center gap-2 rounded-full bg-emerald-500 px-3 py-1.5">
              <Activity size={14} /> Auto Q&A
            </span>
          )}
          <span className="flex h-8 items-end gap-1 rounded-full bg-black/35 px-3 py-1.5">
            {[12, 18, 24, 16].map((height, index) => (
              <i
                key={index}
                className="audio-bar w-1 origin-bottom rounded-full bg-cyan-200"
                style={{ height }}
              />
            ))}
          </span>
        </div>
      </div>
    </div>
  );
}

function ProductDock() {
  return (
    <div className="absolute bottom-5 left-5 right-5 flex items-center gap-3 rounded-lg bg-white/78 p-3 shadow-lg backdrop-blur">
      <div className="grid size-14 place-items-center rounded-md bg-slate-200 text-slate-600">
        <Package size={24} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-extrabold text-slate-700">{product.name}</p>
        <p className="text-sm font-extrabold text-violetLive">{product.price}</p>
      </div>
      <ShoppingBag size={22} className="text-slate-700" />
    </div>
  );
}

function ChannelBadge({
  label,
  status,
  active = false,
  accent = "indigo",
}: {
  label: string;
  status: string;
  active?: boolean;
  accent?: "indigo" | "orange";
}) {
  const color =
    accent === "orange"
      ? "bg-orange-100 text-orange-500"
      : "bg-indigo-100 text-indigo-500";

  return (
    <div
      className={`rounded-lg border bg-white p-2 ${
        active ? "border-violetLive" : "border-slate-200"
      }`}
    >
      <div className="flex items-center gap-2">
        <div
          className={`grid size-8 place-items-center rounded-full ${
            active ? "bg-black text-white" : color
          }`}
        >
          {active ? <Radio size={14} /> : <Link2 size={14} />}
        </div>
        <div className="min-w-0">
          <p className="truncate text-[11px] font-bold text-slate-700">{label}</p>
          <p
            className={`text-[10px] font-bold ${
              active ? "text-rose-500" : "text-slate-400"
            }`}
          >
            {status}
          </p>
        </div>
      </div>
    </div>
  );
}

function CommentBubble({ item }: { item: ChatItem }) {
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
}

function AddVideoModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (data: any) => void }) {
  const [fileType, setFileType] = useState("video");
  const [project, setProject] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
        <h3 className="mb-4 text-lg font-bold text-slate-800">Thêm Video Mới</h3>
        
        <div className="mb-4">
          <label className="mb-2 block text-sm font-semibold text-slate-700">Loại nội dung upload</label>
          <select value={fileType} onChange={e => setFileType(e.target.value)} className="w-full rounded-md border border-slate-300 p-2 text-sm outline-none focus:border-violetLive">
            <option value="video">Video</option>
            <option value="image">Image</option>
            <option value="text">Text</option>
          </select>
        </div>

        <div className="mb-4">
          <label className="mb-2 block text-sm font-semibold text-slate-700">Tải tệp lên</label>
          <div className="flex h-24 cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed border-slate-300 bg-slate-50 hover:bg-slate-100 transition">
            <Plus size={24} className="mb-2 text-slate-400" />
            <span className="text-xs font-semibold text-slate-500">Kéo thả hoặc click để chọn tệp</span>
          </div>
        </div>

        <div className="mb-6">
          <label className="mb-2 block text-sm font-semibold text-slate-700">Chọn project có sẵn</label>
          <select value={project} onChange={e => setProject(e.target.value)} className="w-full rounded-md border border-slate-300 p-2 text-sm outline-none focus:border-violetLive">
            <option value="">-- Chọn Project --</option>
            <option value="p1">Gel tẩy da chết cà phê (Dataset RAG)</option>
            <option value="p2">Kem dưỡng ẩm nha đam</option>
          </select>
        </div>

        <div className="flex justify-end gap-3">
          <button onClick={onClose} className="rounded-md px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 transition">Hủy</button>
          <button onClick={() => onSubmit({ fileType, project })} className="rounded-md bg-violetLive px-4 py-2 text-sm font-semibold text-white transition hover:bg-violet-700">Tạo video</button>
        </div>
      </div>
    </div>
  )
}

function ActionSelectVideoModal({ 
  assets, 
  onClose, 
  onSelect 
}: { 
  assets: any[]; 
  onClose: () => void; 
  onSelect: (asset: any) => void; 
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl">
        <h3 className="mb-4 text-lg font-bold text-slate-800">Chọn Video từ Kho Nội Dung</h3>
        
        <div className="grid grid-cols-2 gap-4">
          {assets.map(asset => (
            <div key={asset.id} onClick={() => !asset.isCreating && onSelect(asset)} className={`cursor-pointer rounded-md border-2 p-3 transition ${asset.isCreating ? 'opacity-50 cursor-not-allowed border-transparent' : 'border-slate-100 bg-slate-50 hover:border-violetLive'}`}>
              <p className="text-sm font-bold text-slate-800">{asset.title}</p>
              <p className="text-xs text-slate-500 mt-1">{asset.duration}</p>
              {asset.isCreating && <p className="text-[10px] text-amber-500 font-bold mt-2">Đang tạo...</p>}
            </div>
          ))}
        </div>

        <div className="mt-6 flex justify-end">
          <button onClick={onClose} className="rounded-md px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 transition">Hủy</button>
        </div>
      </div>
    </div>
  )
}
