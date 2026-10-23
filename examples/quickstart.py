import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["HEDRA_API_KEY"],
    base_url="https://api.hedra.com/v3",
    timeout=130.0,
    max_retries=0,
)
response = client.chat.completions.create(
    model="glm-5.3",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "List the visible objects and their spatial relationships. Describe only what the image shows."},
            {"type": "image_url", "image_url": {"url": "https://imagedelivery.net/yn_JX_LzJpQI9TTynGwR_Q/www-redesign/training/hero-robot-lab-20261019/public"}},
        ],
    }],
    reasoning_effort="low",
    max_tokens=4096,
)
choice = response.choices[0]
if choice.finish_reason != "stop" or not choice.message.content:
    raise RuntimeError(f"No complete answer; finish_reason={choice.finish_reason}")
print(choice.message.content)
