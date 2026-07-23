/**
 * Pull real PLX raw-material costs for a brief.
 *
 * Usage (copy into portal/tmp first so `pg` resolves, then run from portal/):
 *   Copy-Item .cursor/skills/brief-to-quote/scripts/pull-raw-costs.ts portal/tmp/ -Force
 *   cd portal; npx tsx tmp/pull-raw-costs.ts "squalane,jojoba,grapeseed,bakuchiol"
 *
 * Requires $env:DATABASE_URL (see SKILL.md "Pull real costs" for the AWS secret recipe).
 * Reads Prisma tables only: app_product / app_supplier_product / app_rate_settings.
 */
import pg from "pg";
import { writeFileSync } from "node:fs";
const { Client } = pg;

function stripSslmode(u: string): string {
  return u
    .replace(/([?&])sslmode=[^&]*(&|$)/i, (_m, p1, p2) => (p2 === "&" ? p1 : ""))
    .replace(/[?&]$/, "");
}
function median(ns: number[]): number {
  if (!ns.length) return 0;
  const s = [...ns].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}
const round = (n: number, d = 2) => Math.round(n * 10 ** d) / 10 ** d;

const DEFAULT_TERMS =
  "squalane,jojoba,rosehip,grapeseed,argan,marula,bakuchiol,tetrahexyldecyl,ascorbate,tocopherol,caffeine,guarana,mica,fragrance";

async function main() {
  const url = process.env.DATABASE_URL;
  if (!url) {
    console.error("DATABASE_URL not set — see SKILL.md DB recipe (AWS Secrets Manager).");
    process.exit(1);
  }
  const terms = (process.argv[2] ?? DEFAULT_TERMS)
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);

  const client = new Client({ connectionString: stripSslmode(url), ssl: { rejectUnauthorized: false } });
  await client.connect();

  const rateSettings = (await client.query("SELECT * FROM app_rate_settings LIMIT 1")).rows[0] ?? null;

  const sql = `
    SELECT p.code, p.name, p.unit_cost, p.uom,
           sp.system_cost, sp.unit_cost AS supplier_unit_cost, sp.currency, sp.is_preferred
    FROM app_product p
    LEFT JOIN LATERAL (
      SELECT system_cost, unit_cost, currency, is_preferred
      FROM app_supplier_product s
      WHERE s.product_id = p.id AND s.is_active = true
      ORDER BY s.is_preferred DESC NULLS LAST, COALESCE(s.system_cost, s.unit_cost) ASC NULLS LAST
      LIMIT 1
    ) sp ON true
    WHERE p.product_type = 'RAW_MATERIAL' AND p.is_active = true AND p.blocked = false
      AND p.unit_cost > 0
      AND (p.name ILIKE $1 OR p.inci_name ILIKE $1)
    ORDER BY p.unit_cost ASC
    LIMIT 8`;

  const materials: Record<string, unknown> = {};
  for (const term of terms) {
    const rows = (await client.query(sql, [`%${term}%`])).rows as Array<Record<string, unknown>>;
    const costs = rows.map((r) => Number(r.unit_cost));
    materials[term] = {
      count: rows.length,
      minCost: costs.length ? round(Math.min(...costs)) : null,
      medianCost: costs.length ? round(median(costs)) : null,
      cheapest: rows.map((r) => ({
        code: r.code,
        name: String(r.name).slice(0, 64),
        unitCost: round(Number(r.unit_cost)),
        supplier:
          r.system_cost != null || r.supplier_unit_cost != null
            ? {
                cost: round(Number(r.system_cost ?? r.supplier_unit_cost)),
                currency: r.currency,
                preferred: Boolean(r.is_preferred),
              }
            : null,
      })),
    };
  }

  // Write full detail to a file (avoids stdout truncation on big briefs); print a compact summary.
  const outPath = process.argv[3] ?? "raw-costs.json";
  writeFileSync(outPath, JSON.stringify({ rateSettings, materials }, null, 2));
  const rs = (rateSettings ?? {}) as Record<string, unknown>;
  console.log(`Wrote ${Object.keys(materials).length} material groups -> ${outPath}`);
  console.log(
    `RateSettings: waste=${rs.raw_materials_adjustment_rate}% OH/hr=${rs.overhead_per_production_hour} ` +
      `assembly/hr=${rs.assembly_quoting_labor_rate} batching/hr=${rs.batching_quoting_labor_rate}`
  );
  for (const [term, v] of Object.entries(materials)) {
    const m = v as {
      count: number; minCost: number | null; medianCost: number | null;
      cheapest: Array<{ code: string; name: string; unitCost: number; supplier: { cost: number; currency: string } | null }>;
    };
    const t = m.cheapest[0];
    const top = t ? `${t.code} ${t.name.slice(0, 38)} $${t.unitCost}${t.supplier ? " " + t.supplier.currency : ""}` : "(none in catalog)";
    console.log(`  ${term}: count=${m.count} min=${m.minCost ?? "-"} med=${m.medianCost ?? "-"} | ${top}`);
  }
  await client.end();
}

main().catch((e) => {
  console.error("QUERY_ERROR", (e as Error)?.message ?? e);
  process.exit(1);
});
