#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";

const REQUIRED_KEYS = [
  "appDir",
  "tokenCheck",
  "componentMap",
  "routesGlob",
  "renderGuard",
  "a11yAllowlist",
  "viewports",
  "baseUrlEnv",
  "authBypassEnv",
  "previewCommand",
];

function pass(message) {
  console.log(`PASS: ${message}`);
}

function fail(message) {
  console.error(`FAIL: ${message}`);
}

function usage() {
  console.log(
    "usage:\n" +
      "  node .cursor/skills/ui-ux-design-loop/scripts/ui-loop-config.mjs --selftest\n" +
      "  node .cursor/skills/ui-ux-design-loop/scripts/ui-loop-config.mjs --validate <path>\n" +
      "  node .cursor/skills/ui-ux-design-loop/scripts/ui-loop-config.mjs --key <dotpath>",
  );
}

function isPlainObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validateAllowedKeys(obj, allowed, path, errors) {
  for (const key of Object.keys(obj)) {
    if (!allowed.includes(key)) {
      errors.push(`${path} has unknown key '${key}'`);
    }
  }
}

function validateString(value, path, errors) {
  if (typeof value !== "string" || value.trim() === "") {
    errors.push(`${path} must be a non-empty string`);
  }
}

function validateStringArray(value, path, errors, minItems = 0) {
  if (!Array.isArray(value)) {
    errors.push(`${path} must be an array`);
    return;
  }
  if (value.length < minItems) {
    errors.push(`${path} must contain at least ${minItems} item(s)`);
    return;
  }
  for (let idx = 0; idx < value.length; idx += 1) {
    validateString(value[idx], `${path}[${idx}]`, errors);
  }
}

function validateManifestShape(config) {
  const errors = [];

  if (!isPlainObject(config)) {
    return ["config root must be an object"];
  }

  validateAllowedKeys(config, REQUIRED_KEYS, "config", errors);
  for (const key of REQUIRED_KEYS) {
    if (!(key in config)) {
      errors.push(`config is missing required key '${key}'`);
    }
  }

  validateString(config.appDir, "appDir", errors);
  validateString(config.routesGlob, "routesGlob", errors);
  validateString(config.a11yAllowlist, "a11yAllowlist", errors);
  validateString(config.baseUrlEnv, "baseUrlEnv", errors);
  validateString(config.authBypassEnv, "authBypassEnv", errors);
  validateString(config.previewCommand, "previewCommand", errors);
  validateStringArray(config.componentMap, "componentMap", errors);
  validateStringArray(config.viewports, "viewports", errors, 1);

  if (!isPlainObject(config.tokenCheck)) {
    errors.push("tokenCheck must be an object");
  } else {
    const allowedTokenCheck = ["command", "args", "fileGlobs"];
    validateAllowedKeys(config.tokenCheck, allowedTokenCheck, "tokenCheck", errors);
    for (const key of allowedTokenCheck) {
      if (!(key in config.tokenCheck)) {
        errors.push(`tokenCheck is missing required key '${key}'`);
      }
    }
    validateString(config.tokenCheck.command, "tokenCheck.command", errors);
    validateStringArray(config.tokenCheck.args, "tokenCheck.args", errors, 1);
    validateStringArray(config.tokenCheck.fileGlobs, "tokenCheck.fileGlobs", errors, 1);
  }

  if (!isPlainObject(config.renderGuard)) {
    errors.push("renderGuard must be an object");
  } else {
    const allowedRenderGuard = ["authHeading", "errorHeading"];
    validateAllowedKeys(config.renderGuard, allowedRenderGuard, "renderGuard", errors);
    for (const key of allowedRenderGuard) {
      if (!(key in config.renderGuard)) {
        errors.push(`renderGuard is missing required key '${key}'`);
      }
    }
    validateString(config.renderGuard.authHeading, "renderGuard.authHeading", errors);
    validateString(config.renderGuard.errorHeading, "renderGuard.errorHeading", errors);
  }

  return errors;
}

function loadJson(path, label) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    throw new Error(`Could not read ${label} at ${path}: ${error.message}`);
  }
}

function resolveRepoRoot() {
  const envRoot = process.env.UI_LOOP_REPO_ROOT?.trim();
  if (envRoot) {
    return resolve(envRoot);
  }

  try {
    const gitRoot = execFileSync("git", ["rev-parse", "--show-toplevel"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    if (gitRoot) {
      return resolve(gitRoot);
    }
  } catch {
    // Fall through to process.cwd().
  }

  return resolve(process.cwd());
}

function resolveConfiguredPath(pathValue) {
  if (!pathValue) {
    return "";
  }
  return isAbsolute(pathValue) ? pathValue : resolve(process.cwd(), pathValue);
}

function resolveActiveConfigPath(repoRoot) {
  const envPath = resolveConfiguredPath(process.env.UI_LOOP_CONFIG?.trim());
  if (envPath) {
    if (!existsSync(envPath)) {
      throw new Error(`UI_LOOP_CONFIG is set but file does not exist: ${envPath}`);
    }
    return envPath;
  }

  const repoDefault = resolve(repoRoot, "ui-loop.config.json");
  if (existsSync(repoDefault)) {
    return repoDefault;
  }

  throw new Error("Could not resolve config: set UI_LOOP_CONFIG or add ui-loop.config.json at repo root.");
}

function validateConfigObject(config, sourceLabel) {
  const errors = validateManifestShape(config);
  if (errors.length > 0) {
    fail(`${sourceLabel} is invalid`);
    for (const error of errors) {
      fail(`  - ${error}`);
    }
    return false;
  }
  pass(`${sourceLabel} is valid`);
  return true;
}

function runValidate(configPath) {
  const absolutePath = resolveConfiguredPath(configPath);
  if (!absolutePath) {
    fail("Missing path for --validate");
    return 1;
  }
  if (!existsSync(absolutePath)) {
    fail(`Config file not found: ${absolutePath}`);
    return 1;
  }
  const config = loadJson(absolutePath, "config");
  return validateConfigObject(config, `config ${absolutePath}`) ? 0 : 1;
}

function resolveDotPath(input, dotPath) {
  let current = input;
  for (const segment of dotPath.split(".").filter(Boolean)) {
    if (current === null || typeof current !== "object" || !(segment in current)) {
      return { found: false, value: undefined };
    }
    current = current[segment];
  }
  return { found: true, value: current };
}

function runKey(dotPath) {
  if (!dotPath) {
    fail("Missing dot path for --key");
    return 1;
  }

  try {
    const repoRoot = resolveRepoRoot();
    const configPath = resolveActiveConfigPath(repoRoot);
    const config = loadJson(configPath, "config");
    const isValid = validateConfigObject(config, `config ${configPath}`);
    if (!isValid) {
      return 1;
    }

    const resolved = resolveDotPath(config, dotPath);
    if (!resolved.found) {
      fail(`Key not found: ${dotPath}`);
      return 1;
    }

    const { value } = resolved;
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean" || value === null) {
      console.log(String(value));
    } else {
      console.log(JSON.stringify(value, null, 2));
    }
    return 0;
  } catch (error) {
    fail(error.message);
    return 1;
  }
}

function runSelftest() {
  try {
    const repoRoot = resolveRepoRoot();
    const schemaPath = resolve(repoRoot, "ui-loop.schema.json");
    if (!existsSync(schemaPath)) {
      fail(`Schema not found: ${schemaPath}`);
      return 1;
    }
    loadJson(schemaPath, "schema");
    pass(`schema loaded: ${schemaPath}`);

    const configPath = resolveActiveConfigPath(repoRoot);
    const referenceConfig = loadJson(configPath, "config");
    const referenceOk = validateConfigObject(referenceConfig, `reference config ${configPath}`);

    const syntheticConfig = {
      appDir: "apps/example-web",
      tokenCheck: {
        command: "python3",
        args: ["scripts/check-theme-tokens.py"],
        fileGlobs: ["apps/example-web/src/*.ts"],
      },
      componentMap: ["SharedButton"],
      routesGlob: "apps/example-web/e2e/helpers/ui-loop/*.routes.ts",
      renderGuard: {
        authHeading: "Sign in",
        errorHeading: "Something went wrong",
      },
      a11yAllowlist: "apps/example-web/e2e/ui-a11y-allowlist.json",
      viewports: ["chromium"],
      baseUrlEnv: "E2E_BASE_URL",
      authBypassEnv: "LOCAL_AUTH_BYPASS",
      previewCommand: "npm run dev",
    };
    const syntheticOk = validateConfigObject(syntheticConfig, "synthetic minimal config");

    if (referenceOk && syntheticOk) {
      pass("selftest complete");
      return 0;
    }
    fail("selftest failed");
    return 1;
  } catch (error) {
    fail(error.message);
    return 1;
  }
}

function main() {
  const args = process.argv.slice(2);
  if (args.length === 1 && args[0] === "--selftest") {
    process.exit(runSelftest());
  }

  if (args.length === 2 && args[0] === "--validate") {
    process.exit(runValidate(args[1]));
  }

  if (args.length === 2 && args[0] === "--key") {
    process.exit(runKey(args[1]));
  }

  usage();
  process.exit(1);
}

main();
