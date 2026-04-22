const fs = require("fs/promises");
const path = require("path");

const CleanCSS = require("clean-css");
const { minify: minifyHtml } = require("html-minifier-terser");
const terser = require("terser");

const ROOT = __dirname;
const SRC_DIR = path.join(ROOT, "www");
const OUT_DIR = path.join(ROOT, "www_dist");
const JS_EXTENSIONS = new Set([".js"]);
const CSS_EXTENSIONS = new Set([".css"]);
const HTML_EXTENSIONS = new Set([".html"]);

async function removeDir(target) {
  await fs.rm(target, { recursive: true, force: true });
}

async function ensureDir(target) {
  await fs.mkdir(target, { recursive: true });
}

async function buildJs(content, relativePath) {
  const result = await terser.minify(content, {
    compress: {
      passes: 2,
      drop_console: false,
    },
    mangle: true,
    format: {
      comments: false,
    },
  });
  if (result.error) {
    throw new Error(`JS 压缩失败: ${relativePath}: ${result.error.message}`);
  }
  return result.code ?? "";
}

function buildCss(content) {
  const result = new CleanCSS({ level: 2 }).minify(content);
  if (result.errors.length) {
    throw new Error(`CSS 压缩失败: ${result.errors.join("; ")}`);
  }
  return result.styles;
}

async function buildHtml(content) {
  return minifyHtml(content, {
    collapseWhitespace: true,
    removeComments: true,
    minifyCSS: false,
    minifyJS: false,
    keepClosingSlash: true,
  });
}

async function buildFile(srcPath, outPath, relativePath) {
  const ext = path.extname(srcPath).toLowerCase();

  if (HTML_EXTENSIONS.has(ext) || CSS_EXTENSIONS.has(ext) || JS_EXTENSIONS.has(ext)) {
    const content = await fs.readFile(srcPath, "utf8");
    let output = content;
    if (HTML_EXTENSIONS.has(ext)) {
      output = await buildHtml(content);
    } else if (CSS_EXTENSIONS.has(ext)) {
      output = buildCss(content);
    } else if (JS_EXTENSIONS.has(ext)) {
      output = await buildJs(content, relativePath);
    }
    await fs.writeFile(outPath, output, "utf8");
    return;
  }

  await fs.copyFile(srcPath, outPath);
}

async function walk(currentDir, relativeDir = "") {
  const entries = await fs.readdir(currentDir, { withFileTypes: true });
  for (const entry of entries) {
    const relativePath = path.join(relativeDir, entry.name);
    const srcPath = path.join(currentDir, entry.name);
    const outPath = path.join(OUT_DIR, relativePath);

    if (entry.isDirectory()) {
      await ensureDir(outPath);
      await walk(srcPath, relativePath);
      continue;
    }

    await ensureDir(path.dirname(outPath));
    await buildFile(srcPath, outPath, relativePath);
  }
}

async function main() {
  await removeDir(OUT_DIR);
  await ensureDir(OUT_DIR);
  await walk(SRC_DIR);
  console.log(`Built ${SRC_DIR} -> ${OUT_DIR}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
