import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Root CLAUDE.md is the single source of truth; don't auto-generate a second.
  agentRules: false,
};

export default nextConfig;
