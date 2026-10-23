import OpenAI from "openai";

const apiKey = process.env.HEDRA_API_KEY;
if (!apiKey) throw new Error("Set HEDRA_API_KEY first");
const client = new OpenAI({
  apiKey,
  baseURL: "https://api.hedra.com/v3",
  timeout: 130_000,
  maxRetries: 0,
});
const response = await client.chat.completions.create({
  model: "glm-5.3",
  messages: [{
    role: "user",
    content: [
      { type: "text", text: "List the visible objects and their spatial relationships. Describe only what the image shows." },
      { type: "image_url", image_url: { url: "https://imagedelivery.net/yn_JX_LzJpQI9TTynGwR_Q/www-redesign/training/hero-robot-lab-20261019/public" } },
    ],
  }],
  reasoning_effort: "low",
  max_tokens: 4096,
});
const choice = response.choices[0];
if (choice?.finish_reason !== "stop" || !choice.message.content) {
  throw new Error(`No complete answer; finish_reason=${choice?.finish_reason}`);
}
console.log(choice.message.content);
