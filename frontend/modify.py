import json
import re
import sys

try:
    with open('f:/ANHTHU/1-HCMUS/CONTEST/SEAHACKATHON/ai-service/frontend/app/components/live-studio.tsx', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update Layout
    content = content.replace(
        '    <main className="min-h-screen w-screen max-w-[100vw] overflow-x-hidden p-1 text-ink md:p-3 lg:h-screen lg:overflow-hidden">\n      <div className="grid min-h-[calc(100vh-8px)] w-full max-w-full min-w-0 grid-cols-[minmax(0,1fr)] overflow-hidden rounded-lg border-4 border-violetLive bg-[#fbf7fb] shadow-live md:min-h-[calc(100vh-24px)] md:border-[6px] lg:h-[calc(100vh-24px)] lg:min-h-0 lg:grid-cols-[280px_minmax(460px,1fr)_360px]">',
        '    <main className="min-h-screen w-screen max-w-[100vw] overflow-x-hidden text-ink lg:h-screen lg:overflow-hidden bg-[#fbf7fb]">\n      <div className="grid min-h-screen w-full max-w-full min-w-0 grid-cols-[minmax(0,1fr)] overflow-hidden shadow-live lg:min-h-0 lg:grid-cols-[280px_minmax(460px,1fr)_360px]">'
    )

    # 2. Add states to LiveStudio
    old_state = '''  const [isGenerating, setIsGenerating] = useState(false);
  const [comments, setComments] = useState<ChatItem[]>(() =>
    initialComments.slice(0, 4).map(toChatItem),
  );'''

    new_state = '''  const [isGenerating, setIsGenerating] = useState(false);
  const [assets, setAssets] = useState([
    { id: 1, title: "LIVE LOOP", duration: "15s", icon: "Radio", active: true, bars: true },
    { id: 2, title: "45s", duration: "Q&A cut", icon: "BarChart3", bars: true },
    { id: 3, title: "01:20", duration: "Waiting room", icon: "Clapperboard", muted: true },
  ]);
  const [isAddVideoModalOpen, setIsAddVideoModalOpen] = useState(false);
  const [actionModal, setActionModal] = useState<{ isOpen: boolean; actionType: "live" | "schedule" | "generate" | null }>({ isOpen: false, actionType: null });
  const [selectedVideo, setSelectedVideo] = useState<any | null>(null);

  const [comments, setComments] = useState<ChatItem[]>(() =>
    initialComments.slice(0, 4).map(toChatItem),
  );'''

    content = content.replace(old_state, new_state)

    # 3. Update 'Kho noi dung'
    old_kho_noi_dung = '''            <div className="space-y-3">
              <AssetCard
                active
                title="LIVE LOOP"
                duration="15s"
                icon={<Radio size={18} />}
                bars
              />
              <AssetCard
                title="45s"
                duration="Q&A cut"
                icon={<BarChart3 size={18} />}
                bars
              />
              <AssetCard
                muted
                title="01:20"
                duration="Waiting room"
                icon={<Clapperboard size={18} />}
              />
            </div>'''

    new_kho_noi_dung = '''            <div className="space-y-3">
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
            </div>'''
    content = content.replace(old_kho_noi_dung, new_kho_noi_dung)

    # 4. Update '+ Video' button
    content = content.replace(
        '''            <button
              type="button"
              className="flex h-12 w-full items-center justify-center gap-2 rounded-md border border-slate-200 bg-white text-sm font-semibold text-slate-700"
            >
              <Plus size={16} /> Video
            </button>''',
        '''            <button
              type="button"
              onClick={() => setIsAddVideoModalOpen(true)}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-md border border-slate-200 bg-white text-sm font-semibold text-slate-700"
            >
              <Plus size={16} /> Video
            </button>'''
    )

    # 5. Remove Gen AI component
    content = content.replace(
'''          <VideoActionCard
            generating={isGenerating}
            onGenerate={generateVideo}
          />''', 
''
    )

    # 6. Default video view & Modals in LiveStudio return
    old_video_section = '''            <div className="relative aspect-[9/13] overflow-hidden rounded-xl bg-[#101827]">
              <video
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

              <div className="pointer-events-none absolute inset-0 scanline" />

              {isLive ? (
                <LiveOverlay
                  answer={pinnedAnswer}
                  generating={isGenerating}
                  viewers={comments.length * 37 + 412}
                />
              ) : (
                <ReadyState
                  onStart={startLive}
                  onSchedule={scheduleLive}
                  onGenerate={generateVideo}
                />
              )}

              <ProductDock />
            </div>'''

    new_video_section = '''            <div className="relative aspect-[9/13] overflow-hidden rounded-xl bg-[#101827]">
              {selectedVideo ? (
                <video
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
              )}

              <div className="pointer-events-none absolute inset-0 scanline" />

              {isLive ? (
                <LiveOverlay
                  answer={pinnedAnswer}
                  generating={isGenerating}
                  viewers={comments.length * 37 + 412}
                />
              ) : (
                <ReadyState
                  onStart={() => setActionModal({ isOpen: true, actionType: "live" })}
                  onSchedule={() => setActionModal({ isOpen: true, actionType: "schedule" })}
                  onGenerate={() => setActionModal({ isOpen: true, actionType: "generate" })}
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
            )}'''

    content = content.replace(old_video_section, new_video_section)

    # 7. Add Modal Components & update AssetCard at the end
    new_components = '''
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
'''

    content = re.sub(
        r'function VideoActionCard.*?}\n\nfunction AssetCard',
        'function AssetCard',
        content,
        flags=re.DOTALL
    )

    # Update AssetCard definition
    old_assetcard = '''function AssetCard({
  title,
  duration,
  icon,
  active = false,
  muted = false,
  bars = false,
}: {
  title: string;
  duration: string;
  icon: React.ReactNode;
  active?: boolean;
  muted?: boolean;
  bars?: boolean;
}) {'''

    new_assetcard = '''function AssetCard({
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
'''
    content = content.replace(old_assetcard, new_assetcard)
    content = content.replace('{icon}', '{getIcon()}')
    
    if isCreating_code_added := True:
        # We need to render a "Creating" overlay or something in AssetCard if isCreating is true
        content = content.replace(
            '''<span>{active ? duration : title}</span>''',
            '''<span>{active ? duration : title}</span>
        {isCreating && <span className="ml-2 rounded-sm bg-amber-500 px-1.5 py-0.5 text-white">Đang tạo</span>}'''
        )

    content += new_components

    with open('f:/ANHTHU/1-HCMUS/CONTEST/SEAHACKATHON/ai-service/frontend/app/components/live-studio.tsx', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Success")
except Exception as e:
    print("Error:", e)
    sys.exit(1)
