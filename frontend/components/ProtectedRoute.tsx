"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { firebaseUser, profile, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !firebaseUser) {
      router.replace("/login");
    }
  }, [loading, firebaseUser, router]);

  if (loading || !firebaseUser || !profile) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-slate-500">
        Loading...
      </div>
    );
  }

  return <>{children}</>;
}
