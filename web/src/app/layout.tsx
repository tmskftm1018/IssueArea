import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import "./visual-overrides.css";
export const metadata: Metadata = { title: "IssueArea | 대한민국 최신 뉴스 지도", description: "지역과 주제로 탐색하는 대한민국 최신 뉴스" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
