"use client";

import * as Sentry from "@sentry/nextjs";
import Link from "next/link";
import { useEffect } from "react";

export default function NotFound() {
  useEffect(() => {
    // Report to Sentry that a page was not found
    Sentry.captureMessage("404 - Page not found", "warning");
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center text-center">
      <h1 className="text-4xl font-bold">404 - Page Not Found</h1>
      <p className="mt-4 text-lg">Sorry, the page you're looking for doesn't exist.</p>
      <Link href="/" className="mt-8 rounded bg-blue-500 px-4 py-2 text-white hover:bg-blue-600">
        Return Home
      </Link>
    </div>
  );
} 