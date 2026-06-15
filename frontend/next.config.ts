import type { NextConfig } from "next";

// Server-side only (not exposed to the browser). On Vercel, set this to your
// Render backend URL, e.g. https://classroom-agent.onrender.com
// Locally it defaults to the FastAPI dev server.
const BACKEND_URL = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        // Proxy every /api/* request (including the OAuth login/callback
        // redirects) through this Next.js app to the FastAPI backend. The
        // browser only ever talks to its own origin, so the session cookie
        // set during Google sign-in is a first-party cookie — no
        // cross-site / third-party cookie issues.
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
