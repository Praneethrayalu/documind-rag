# EC2 deployment checklist (not a deployment record)

No EC2 instance was created for this project. AWS accounts, free-tier eligibility and prices differ. A free-tier badge is not a guarantee of zero cost: compute, EBS storage, public IPv4, snapshots, NAT gateways and transfer can each create charges. Check the live AWS console and pricing for the selected account/region first. Do not launch until the owner explicitly accepts the final configuration and possible charges.

1. Run locally first. Keep private PDFs off an internet-accessible demo.
2. Review IAM permissions and choose an existing least-privilege role. Do not put AWS keys in this repo, Docker image, user data, or a public `.env`.
3. Estimate RAM from representative PDFs. CPU embeddings avoid a GPU but still consume memory. Do not assume a tiny free instance can run PyTorch and a local LLM reliably.
4. If authorized, install Docker on an approved Ubuntu instance and clone the private repository using a least-privilege route. Build the image and run the README command bound to `127.0.0.1`.
5. Prefer an SSH tunnel (`ssh -L 8501:localhost:8501 ...`) for a personal demo. Do not open 8501 to the internet. A public service needs a TLS reverse proxy, authentication, request limits, upload sandboxing and a security review beyond this project.
6. Verify the Docker health check, upload the synthetic sample PDF, ask a question, and inspect the page citations. Record date, region, instance type, image digest and actual observed URL before claiming deployment.
7. Configure a budget alarm and a stop/termination plan. Stopping compute does not necessarily remove storage or IP costs. Check all created resources and billing after cleanup.

A laptop-only demo is the supported zero-cloud-cost path. Docker support and this checklist are provided separately from any deployment claim.
