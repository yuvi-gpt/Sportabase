import * as esbuild from "esbuild";

const watchMode = process.argv.includes("--watch");

const buildOptions = {
  entryPoints: ["src/content/index.js"],
  bundle: true,
  outfile: "dist/content.js",
  format: "iife",
  platform: "browser",
  target: ["chrome120"],
  sourcemap: true,
  minify: false,
  legalComments: "none",
  logLevel: "info",
};

if (watchMode) {
  const buildContext = await esbuild.context(buildOptions);
  await buildContext.watch();

  console.log("[sportabase] Watching extension source files...");
} else {
  await esbuild.build(buildOptions);
}
