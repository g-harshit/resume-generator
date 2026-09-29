import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // @rg/schema ships TypeScript source (generated from the backend), not built JS.
  transpilePackages: ["@rg/schema"],
  // Dev only: also serve dev assets to http://127.0.0.1:3100 (a separate origin, so a
  // second account can be signed in beside the one on localhost).
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
