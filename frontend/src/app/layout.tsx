import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "Gullak — AI Financial Life Coach",
  description: "Behavioral financial intelligence that understands your spending personality.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased dark`}>
      <body className="min-h-full flex flex-col">
        {children}
        <Toaster
          position="top-center"
          toastOptions={{
            style: {
              background: "rgba(13,13,26,0.95)",
              border: "1px solid rgba(124,58,237,0.3)",
              color: "#e2e8f0",
              backdropFilter: "blur(20px)",
            },
          }}
        />
      </body>
    </html>
  );
}
