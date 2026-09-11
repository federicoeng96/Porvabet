import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Porvabet — Analisi pre-match",
  description: "Motore quantitativo di analisi pre-match per scommesse sportive",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="it">
      <body>{children}</body>
    </html>
  );
}
