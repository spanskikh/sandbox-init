# Sandbox Init (`spanskikh`)

Symmetric local-first baseline for neuro-symbolic AI QA & data pipelines across the `hippo` / `rhino` cluster.

## Cluster Nodes (Symmetric Hot Standby)
- **hippo** (Primary compute / LLM inference / orchestration): i5-9500, 24 GiB RAM, NVMe
- **rhino** (Primary stateful storage / DB / background workers): i5-9500, 16 GiB RAM, 687 GB `/mnt/data`
