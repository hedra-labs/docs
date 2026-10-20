import { HedraClient } from "@hedra/sdk";
import { writeFile } from "node:fs/promises";

const key = process.env.HEDRA_API_KEY;
if (!key) throw new Error("Set HEDRA_API_KEY first");
const client = new HedraClient({ apiKey: key });
const ack = await client.jobs.submit("gpt-image-2", {
  input: { prompt: "An industrial inspection camera on a workbench",
    aspect_ratio: "1:1", resolution: "1K", quality: "medium", output_format: "png" },
}, { timeoutInSeconds: 30 });
console.log(`Job: ${ack.job_id}`);
const deadline = Date.now() + 600_000;
while (true) {
  if (Date.now() >= deadline) {
    throw new Error(`Still running: ${ack.job_id}. Resume polling; do not resubmit.`);
  }
  const status = await client.jobs.getStatus(ack.job_id, {}, { timeoutInSeconds: 30 });
  if (status.status === "COMPLETED" || status.status === "FAILED") break;
  await new Promise(resolve => setTimeout(resolve, 5000));
}
const result = await client.jobs.get(ack.job_id, {}, { timeoutInSeconds: 30 });
if (result.status === "FAILED") throw new Error(JSON.stringify(result.error));
const output = result.outputs?.[0];
if (!output || output.status !== "COMPLETED" || !output.url) {
  throw new Error("No downloadable output; inspect the job's output status and error.");
}
// Download without forwarding the API credential to the storage host.
const download = await fetch(output.url, { signal: AbortSignal.timeout(60_000) });
if (!download.ok) throw new Error(`Download failed: ${download.status}`);
await writeFile("output.png", Buffer.from(await download.arrayBuffer()));
console.log("Saved output.png");
