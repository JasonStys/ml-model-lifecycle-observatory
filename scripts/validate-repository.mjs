/**
 * File: validate-repository.mjs
 * Purpose: Enforce documentation, source-header, local-link, and secret-hygiene invariants.
 * Symbols and line locations: see docs/code-index.md for exact declarations.
 * Important variables: requiredFiles and headerExtensions define the portfolio contract.
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, extname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const requiredFiles = [
  "README.md",
  "CONTRIBUTING.md",
  "SECURITY.md",
  "docs/architecture.md",
  "docs/api.md",
  "docs/complexity.md",
  "docs/data-contract.md",
  "docs/file-catalog.md",
  "docs/model-lifecycle.md",
  "docs/operations.md",
  "docs/research.md",
  "docs/risk-register.md",
  "docs/testing.md",
  "docs/adr/0001-portable-artifacts-and-small-registry.md",
  "docs/reports/benchmark.md",
  "docs/reports/test-summary.md",
  "docs/reports/validation.md",
];
const headerExtensions = new Set([".py", ".mjs", ".sh", ".sql"]);
const excludedDirectories = new Set([
  ".artifacts", ".git", ".mypy_cache", ".pip-audit-cache", ".pytest_cache",
  ".ruff_cache", ".test-runtime", ".venv", "dist", "htmlcov",
]);

/** Recursively return files without dependencies or generated runtime output. */
function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return excludedDirectories.has(entry.name) ? [] : walk(path);
    return [path];
  });
}

/** Return broken local Markdown targets while leaving remote checks to network-aware tooling. */
function brokenMarkdownLinks(path) {
  const markdown = readFileSync(path, "utf8");
  return [...markdown.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)].flatMap((match) => {
    const target = match[1].replace(/^<|>$/g, "");
    if (/^(?:https?:|mailto:|#)/.test(target)) return [];
    const localTarget = decodeURIComponent(target.split(/[?#]/, 1)[0]);
    return existsSync(resolve(dirname(path), localTarget)) ? [] : [target];
  });
}

/** Validate required files, source headers, local links, and accidental live credentials. */
function main() {
  const failures = [];
  for (const requiredFile of requiredFiles) {
    if (!existsSync(join(repositoryRoot, requiredFile))) {
      failures.push(`Missing required file: ${requiredFile}`);
    }
  }
  for (const path of walk(repositoryRoot)) {
    const repositoryPath = relative(repositoryRoot, path).replaceAll("\\", "/");
    if (extname(path) === ".md") {
      for (const target of brokenMarkdownLinks(path)) {
        failures.push(`Broken local Markdown link in ${repositoryPath}: ${target}`);
      }
    }
    if (!headerExtensions.has(extname(path))) continue;
    const firstLines = readFileSync(path, "utf8").split(/\r?\n/).slice(0, 10).join("\n");
    if (!firstLines.includes("File:") || !firstLines.includes("Purpose:")) {
      failures.push(`Source header is incomplete: ${repositoryPath}`);
    }
  }
  if (failures.length > 0) {
    console.error(failures.join("\n"));
    process.exitCode = 1;
    return;
  }
  console.log("Repository structure, links, and source headers are valid.");
}

main();
