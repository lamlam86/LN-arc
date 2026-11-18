"use client";

import { useEffect } from "react";

import { auth } from "@/lib/auth";

// Static export cannot use a server-side redirect() from a page: it aborts
// prerendering and writes a Next error shell as index.html. Redirect after
// hydration instead, matching the client-side guards used elsewhere.
export default function Home() {
  useEffect(() => {
    window.location.replace(auth.getToken() ? "/function/tasks" : "/login");
  }, []);
  return null;
}
