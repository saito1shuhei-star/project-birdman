import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Project BirdMan",
  description: "人力飛行機設計支援プラットフォーム",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja">
      <body>
        <main>{children}</main>
      </body>
    </html>
  );
}
