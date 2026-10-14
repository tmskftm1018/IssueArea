import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import "./explorer-design.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL;

export const metadata: Metadata = {
  ...(siteUrl ? { metadataBase: new URL(siteUrl) } : {}),
  title: "IssueArea | 대한민국 최신 뉴스 지도",
  description: "지역과 주제로 탐색하는 대한민국 최신 뉴스",
  openGraph: {
    title: "IssueArea | 대한민국 최신 뉴스 지도",
    description: "지역과 주제로 탐색하는 대한민국 최신 뉴스",
    locale: "ko_KR",
    type: "website",
    ...(siteUrl ? { url: siteUrl } : {}),
  },
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
