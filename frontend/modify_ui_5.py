import re

file_path = 'f:/ANHTHU/1-HCMUS/CONTEST/SEAHACKATHON/ai-service/frontend/app/components/live-studio.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix sidebar overflow
sidebar_old = '''          <section className="mt-5 flex min-h-0 flex-1 flex-col">
            <div className="mb-3 flex shrink-0 items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                Kho nội dung
              </h2>
              <Settings2 size={16} className="text-slate-400" />
            </div>
            <div className="space-y-3 overflow-y-auto pb-4 pr-1">'''
sidebar_new = '''          <section className="mt-5 flex min-h-0 flex-1 flex-col">
            <div className="mb-3 flex shrink-0 items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                Kho nội dung
              </h2>
              <Settings2 size={16} className="text-slate-400" />
            </div>
            <div className="flex-1 min-h-0 space-y-3 overflow-y-auto pb-4 pr-1">'''
content = content.replace(sidebar_old, sidebar_new)

# 2. Update scheduleLive to start the video
schedule_old = '''  function scheduleLive() {
  }'''
schedule_new = '''  function scheduleLive() {
    setIsLive(true);
    setTimeout(() => {
      if (videoRef.current) {
        videoRef.current.play().catch(console.error);
      }
    }, 100);
  }'''
content = content.replace(schedule_old, schedule_new)

# 3. Update the bottom Play/Pause button to also toggle video play state
btn_old = '''            <button
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
              }}'''
btn_new = '''            <button
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
              }}'''
content = content.replace(btn_old, btn_new)


with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
