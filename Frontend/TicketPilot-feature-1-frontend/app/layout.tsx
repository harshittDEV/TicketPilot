import type { Metadata } from 'next';
import './globals.css';
import { AppShell } from '@/components/layout/AppShell';

export const metadata: Metadata = {
  title: 'Tatkal Assistant — Personal Railway Booking Preparation',
  description: 'A thoughtful, accessible personal Indian Railways Tatkal preparation and booking-assistance application with real-time countdown, train comparison, and guided IRCTC readiness.',
  keywords: ['Tatkal Assistant', 'Indian Railways', 'IRCTC preparation', 'train comparison', 'Tatkal countdown'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased bg-background text-ink">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
