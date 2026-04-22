const fs = require("fs");
const path = require("path");

const target = path.join(
  __dirname,
  "..",
  "node_modules",
  "next",
  "dist",
  "compiled",
  "http-proxy",
  "index.js",
);

const legacyNeedle = "r(837)._extend";
const patchedValue = "Object.assign";

function main() {
  if (!fs.existsSync(target)) {
    console.warn(`[patch-next-http-proxy] skipped: file not found: ${target}`);
    return;
  }

  const original = fs.readFileSync(target, "utf8");
  if (!original.includes(legacyNeedle)) {
    console.log("[patch-next-http-proxy] already patched");
    return;
  }

  const patched = original.split(legacyNeedle).join(patchedValue);
  fs.writeFileSync(target, patched, "utf8");
  console.log("[patch-next-http-proxy] patched Next compiled http-proxy");
}

main();
