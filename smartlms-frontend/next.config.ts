import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  turbopack: {
    // Ensuring the root is pinned to the project directory to avoid phantom dependency resolution from parent folders
    // root: "./", // Note: The 'root' property might be implicit or handled differently in some versions, but we'll try to use the recommended keys if available.
  }
};

export default nextConfig;
