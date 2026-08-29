"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { ConnectedAccountsPanel } from "@/components/ConnectedAccountsPanel";
import { useAuth } from "@/components/AuthProvider";

const ERROR_MESSAGES: Record<string, string> = {
  access_denied: "Sign-in was cancelled.",
  invalid_request: "Something went wrong starting the connection. Please try again.",
  invalid_state: "This connection request expired. Please try again.",
  already_connected:
    "This account is already connected to another driveON account. Please use a different account.",
  max_accounts_reached: "You've reached the maximum number of connected accounts for your plan.",
  missing_refresh_token:
    "Offline access wasn't granted. Try removing driveON's access from your account's permissions page and reconnecting.",
  oauth_failed: "Couldn't complete the connection. Please try again.",
};

function DrivesContent() {
  const { refreshProfile } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [banner, setBanner] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    const error = searchParams.get("error");
    const connected = searchParams.get("connected");
    if (error) {
      setBanner({ type: "error", text: ERROR_MESSAGES[error] || "Something went wrong." });
      router.replace("/drives");
    } else if (connected) {
      setBanner({ type: "success", text: "Drive connected." });
      refreshProfile();
      router.replace("/drives");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <Navbar />
      <main className="mx-auto max-w-4xl px-6 py-8">
        {banner && (
          <div
            className={`mb-6 rounded-md px-4 py-3 text-sm ${
              banner.type === "success" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
            }`}
          >
            {banner.text}
          </div>
        )}
        <ConnectedAccountsPanel />
      </main>
    </div>
  );
}

export default function DrivesPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={null}>
        <DrivesContent />
      </Suspense>
    </ProtectedRoute>
  );
}
