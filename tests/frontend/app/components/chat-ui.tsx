"use client";

import React, { useState, useEffect, useRef } from "react";

type Message = {
  id: string;
  sender: "user" | "agent";
  text: string;
};

export default function ChatUI() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string>("new");
  
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    // Determine WebSocket URL
    const wsUrlStr = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/chat";
    const url = `${wsUrlStr}/${sessionId}`;
    
    const ws = new WebSocket(url);

    ws.onopen = () => {
      console.log("Connected to WebSocket");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === "session_id") {
          setSessionId(data.session_id);
        } else if (data.type === "start") {
          setIsStreaming(true);
          // Thêm một message rỗng cho agent để chuẩn bị stream
          setMessages((prev) => [
            ...prev,
            { id: Date.now().toString(), sender: "agent", text: "" },
          ]);
        } else if (data.type === "chunk") {
          // Append chunk to the last agent message
          setMessages((prev) => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            if (lastMessage && lastMessage.sender === "agent") {
              lastMessage.text += data.text;
            }
            return newMessages;
          });
        } else if (data.type === "end") {
          setIsStreaming(false);
        } else if (data.type === "error") {
          setIsStreaming(false);
          setMessages((prev) => [
            ...prev,
            { id: Date.now().toString(), sender: "agent", text: `⚠️ Lỗi: ${data.message}` },
          ]);
        }
      } catch (err) {
        console.error("Error parsing websocket message", err);
      }
    };

    ws.onclose = () => {
      console.log("Disconnected from WebSocket");
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, []); // Kết nối 1 lần khi mount. Lưu ý nếu đổi sessionId thì sẽ reconnect nếu thêm dependency

  const sendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    // Hiển thị tin nhắn người dùng
    setMessages((prev) => [
      ...prev,
      { id: Date.now().toString(), sender: "user", text: input },
    ]);

    // Gửi qua WebSocket
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(input);
    } else {
      console.error("WebSocket is not connected");
    }

    setInput("");
  };

  return (
    <div className="flex flex-col h-[600px] w-full max-w-md mx-auto border rounded-xl shadow-lg bg-white overflow-hidden">
      <div className="bg-indigo-600 text-white p-4 font-bold text-center">
        🛍️ Trợ lý Sales AI
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] p-3 rounded-2xl ${
                msg.sender === "user"
                  ? "bg-indigo-600 text-white rounded-br-none"
                  : "bg-white text-gray-800 border shadow-sm rounded-bl-none"
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
        {isStreaming && (
          <div className="flex justify-start">
            <div className="bg-white text-gray-800 border shadow-sm rounded-2xl rounded-bl-none p-3 max-w-[80%] flex space-x-1 items-center">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span>
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></span>
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.4s" }}></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={sendMessage} className="p-4 bg-white border-t flex space-x-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Nhắn tin cho trợ lý..."
          className="flex-1 px-4 py-2 border rounded-full focus:outline-none focus:ring-2 focus:ring-indigo-500 text-black"
          disabled={isStreaming}
        />
        <button
          type="submit"
          disabled={!input.trim() || isStreaming}
          className="px-4 py-2 bg-indigo-600 text-white rounded-full font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          Gửi
        </button>
      </form>
    </div>
  );
}
