"use client";

import {
  Activity,
  CalendarCheck,
  ListTodo,
  Moon,
  PhoneCall,
  Sun,
  Users,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import useSWR from "swr";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { fetcher } from "@/lib/api";
import type { Envelope, Metrics } from "@/lib/types";

const NAV = [
  { href: "/", label: "Overview", icon: Activity },
  { href: "/calls", label: "Calls", icon: PhoneCall },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/action-queue", label: "Action queue", icon: ListTodo },
  { href: "/bookings", label: "Bookings", icon: CalendarCheck },
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  const { data } = useSWR<Envelope<Metrics>>(
    "/api/metrics?range=today",
    fetcher,
    { refreshInterval: 10_000 },
  );
  const m = data?.data;

  return (
    <header className="bg-background/95 sticky top-0 z-40 border-b backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4">
        <Link href="/" className="flex items-center gap-2">
          <Image
            src="/emma-logo.png"
            alt="Emma — QuantumLoopAI"
            width={400}
            height={100}
            priority
            className="h-12 w-auto dark:invert"
          />
          <span
            className="inline-block size-2 animate-pulse rounded-full bg-emerald-500"
            aria-hidden
          />
          <span className="text-muted-foreground text-xs font-normal">live</span>
        </Link>

        <nav className="flex items-center gap-1">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active =
              pathname === href ||
              (href !== "/" && pathname?.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-accent text-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                <Icon className="size-4" />
                <span className="hidden sm:inline">{label}</span>
              </Link>
            );
          })}
        </nav>

        <Separator orientation="vertical" className="h-6" />

        <div className="text-muted-foreground hidden items-center gap-4 text-xs md:flex">
          <Stat label="calls today" value={m?.calls} />
          <Stat label="contact" value={m?.contact_capture_pct} suffix="%" />
          <Stat label="booked" value={m?.booking_rate_pct} suffix="%" />
        </div>

        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

interface StatProps {
  label: string;
  value: number | undefined;
  suffix?: string;
}

function Stat({ label, value, suffix }: StatProps) {
  return (
    <span>
      <span className="text-foreground font-medium">
        {value ?? "·"}
        {value !== undefined ? suffix ?? "" : ""}
      </span>{" "}
      {label}
    </span>
  );
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const next = theme === "dark" ? "light" : "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} theme`}
    >
      <Sun className="size-4 dark:hidden" />
      <Moon className="hidden size-4 dark:block" />
    </Button>
  );
}
