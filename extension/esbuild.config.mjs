import * as esbuild from "esbuild";

import { fileURLToPath } from "node:url";

const extensionRoot = fileURLToPath(new URL(".", import.meta.url));
const authDefines = {
  __SPORTABASE_CLERK_KEY__: JSON.stringify(process.env.SPORTABASE_CLERK_PUBLISHABLE_KEY || ""),
  __SPORTABASE_SYNC_HOST__: JSON.stringify(process.env.SPORTABASE_CLERK_SYNC_HOST || ""),
  __SPORTABASE_API_BASE__: JSON.stringify(process.env.SPORTABASE_API_BASE || "https://sportabase-api.onrender.com"),
};
const syncHost = process.env.SPORTABASE_CLERK_SYNC_HOST;
const productionBuild = process.env.SPORTABASE_DEPLOYMENT === "production";
if (syncHost && (new URL(syncHost).protocol !== "https:" || new URL(syncHost).origin !== syncHost)) throw new Error("Sync host must be an HTTPS origin.");
if (productionBuild && (!process.env.SPORTABASE_CLERK_PUBLISHABLE_KEY || !syncHost || !process.env.SPORTABASE_API_BASE)) {
  throw new Error("Production extension builds require the Clerk key, exact sync host, and API base.");
}
const backgroundOptions = {
  absWorkingDir:extensionRoot,entryPoints:["background.js"],bundle:true,outfile:"dist/background.js",format:"iife",platform:"browser",target:["chrome120"],
  define:authDefines,minify:false,sourcemap:false,legalComments:"none",
};
const settingsOptions = {
  absWorkingDir:extensionRoot,entryPoints:["src/extension-page/account-settings-page.js"],bundle:true,outfile:"dist/settings.js",
  format:"iife",platform:"browser",target:["chrome120"],minify:false,sourcemap:false,legalComments:"none",
};
const watchMode = process.argv.includes("--watch");

const buildOptions = {
  absWorkingDir: extensionRoot,
  entryPoints: ["src/content/index.js"],
  bundle: true,
  outfile: "dist/content.js",
  format: "iife",
  platform: "browser",
  target: ["chrome120"],
  sourcemap: true,
  sourcesContent: false,
  minify: false,
  legalComments: "none",
  logLevel: "info",
};

if (watchMode) {
  const buildContext = await esbuild.context(buildOptions);
  await buildContext.watch();
  const backgroundContext=await esbuild.context(backgroundOptions);
  await backgroundContext.watch();
  const settingsContext=await esbuild.context(settingsOptions);
  await settingsContext.watch();

  console.log("[sportabase] Watching extension source files...");
} else {
  await esbuild.build(buildOptions);
  await esbuild.build(backgroundOptions);
  await esbuild.build(settingsOptions);
}
