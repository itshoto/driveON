"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { signOut } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { useAuth } from "./AuthProvider";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/drives", label: "My Drives" },
  { href: "/files", label: "My Files" },
];

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { profile } = useAuth();

  const handleSignOut = async () => {
    await signOut(auth);
    router.replace("/login");
  };

  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/dashboard" className="text-lg font-semibold text-brand-600">
          driveON
        </Link>
        <div className="flex items-center gap-6">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`text-sm font-medium ${
                pathname === link.href ? "text-brand-600" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {link.label}
            </Link>
          ))}
          {profile && <span className="text-sm text-slate-500">{profile.username}</span>}
          <button
            onClick={handleSignOut}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  );
}
