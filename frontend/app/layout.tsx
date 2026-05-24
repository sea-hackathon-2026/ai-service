import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Live Commerce Studio",
  description: "Mock UI live commerce agent with local video and RAG comments",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
