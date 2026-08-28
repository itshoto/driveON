import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <h1 className="text-4xl font-bold text-brand-600">driveON</h1>
      <p className="mt-4 max-w-xl text-lg text-slate-600">
        One account. Multiple Google Drives. One unified storage.
      </p>
      <p className="mt-2 max-w-xl text-slate-500">
        Pool up to 5 Google Drive accounts into a single storage system, upload files larger than
        any one account could hold, and ask AI questions about your PDFs.
      </p>
      <div className="mt-8 flex gap-4">
        <Link
          href="/register"
          className="rounded-md bg-brand-600 px-6 py-3 font-medium text-white hover:bg-brand-700"
        >
          Get Started
        </Link>
        <Link
          href="/login"
          className="rounded-md border border-slate-300 px-6 py-3 font-medium text-slate-700 hover:bg-slate-50"
        >
          Login
        </Link>
      </div>
    </main>
  );
}
