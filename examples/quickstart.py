import os
import time
from pathlib import Path

import httpx
from hedra import Hedra

client = Hedra(api_key=os.environ["HEDRA_API_KEY"], timeout=30.0)
ack = client.jobs.submit(
    model="gpt-image-2",
    input={"prompt": "An industrial inspection camera on a workbench",
           "aspect_ratio": "1:1", "resolution": "1K",
           "quality": "medium", "output_format": "png"},
)
print(f"Job: {ack.job_id}", flush=True)
deadline = time.monotonic() + 600
while True:
    if time.monotonic() >= deadline:
        raise TimeoutError(f"Still running: {ack.job_id}. Resume polling; do not resubmit.")
    status = client.jobs.get_status(job_id=ack.job_id)
    if status.status in ("COMPLETED", "FAILED"):
        break
    time.sleep(5)

result = client.jobs.get(job_id=ack.job_id)
if result.status == "FAILED":
    raise RuntimeError(str(result.error))
outputs = result.outputs or []
if not outputs or outputs[0].status != "COMPLETED" or not outputs[0].url:
    raise RuntimeError("No downloadable output; inspect the job's output status and error.")
# Download without forwarding the API credential to the storage host.
with httpx.stream("GET", str(outputs[0].url), timeout=60.0, follow_redirects=True) as response:
    response.raise_for_status()
    with Path("output.png").open("wb") as output:
        for chunk in response.iter_bytes():
            output.write(chunk)
print("Saved output.png")
