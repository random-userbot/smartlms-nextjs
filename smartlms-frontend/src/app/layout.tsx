import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { ActivityProvider } from "@/context/ActivityTracker";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SmartLMS | Cyber-Intelligence Portal",
  description: "Next-generation learning management with real-time engagement tracking and Aika AI Sensei.",
};

import NavigationHub from '@/components/NavigationHub';
import { GlobalBackground } from "@/components/animations/GlobalBackground";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      data-scroll-behavior="smooth"
    >
      <body className="min-h-full flex flex-col bg-background text-foreground transition-colors duration-300 relative">
        <ThemeProvider>
          <ActivityProvider>
            <AuthProvider>
              <GlobalBackground />
              <div className="noise-overlay" />
              <div className="relative z-10 flex-1 flex flex-col">
                {children}
                <NavigationHub />
              </div>
            </AuthProvider>
          </ActivityProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
