// TypeScript's half of the probe tree: a way in, a boundary, a loop and a branch.

export const RETRIES = 3;

export interface Setting {
  key: string;
  value: string;
}

export async function loadConfig(url: string): Promise<Setting[]> {
  const response = await fetch(url);
  const lines = (await response.text()).split("\n");
  const out: Setting[] = [];
  for (const line of lines) {
    if (!line.includes("=")) {
      continue;
    }
    const [key, value] = line.split("=", 2);
    out.push({ key: key.trim(), value: value.trim() });
  }
  return out;
}

export async function main(): Promise<number> {
  const settings = await loadConfig(process.env.PROBE_URL ?? "");
  console.log(`${settings.length} settings`);
  return 0;
}
