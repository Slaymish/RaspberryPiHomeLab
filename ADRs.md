# ADRs

This file contains the full Architecture Decision Records for the homelab.  
Each ADR follows the format: **Status**, **Context**, **Decision**, **Consequences**, **Alternatives**.

---

## ADR 001 — External access via Cloudflare Tunnel and Caddy  
**Status:** Accepted

**Context:** The home ISP uses CGNAT and dynamic IPv4 allocation which makes port forwarding unreliable. Non-technical users need simple, host based HTTP(S) access to household services (for example, photo sharing).

**Decision:** Expose user-facing HTTP(S) services using Cloudflare Tunnel. Terminate TLS, perform host based routing and apply security headers with a local Caddy instance.

**Consequences:**
- Works around CGNAT and provides automatic TLS and virtual host routing.
- Single external dependency on Cloudflare; if the tunnel or Cloudflare control plane has issues public access may be affected.
- Operational tasks: document tunnel recovery steps and add tunnel health monitoring.

**Alternatives:**
- Tailscale HTTP relay or ACLs only (less suitable for public hostnames).
- Rely on ISP port forwarding and dynamic DNS (not viable under CGNAT).
- Self-hosted reverse proxy with static IP (requires different network setup).

---

## ADR 002 — Orchestration: Docker Compose rather than Kubernetes  
**Status:** Accepted

**Context:** Single Raspberry Pi host with limited RAM and CPU. Low operational overhead and simplicity are priorities.

**Decision:** Use Docker Compose for service orchestration, including restart policies and reproducible compose stacks.

**Consequences:**
- Low complexity and small resource footprint.
- Lacks advanced features such as multi-node scheduling, rolling updates and built-in service discovery at cluster scale.
- Mitigation: keep Compose files versioned and document an upgrade path to heavier orchestration if needed.

**Alternatives:**
- Kubernetes (too heavy for a single Pi).
- Docker Swarm or systemd units (either adds complexity or is more manual).

---

## ADR 003 — Backups: rclone crypt to Backblaze B2  
**Status:** Accepted

**Context:** Need encrypted offsite backups with predictable pricing and reasonable reliability.

**Decision:** Use rclone with a `crypt` remote writing to Backblaze B2. Store crypt passwords and keys outside the repo and rotate as appropriate.

**Consequences:**
- Encrypted offsite backups with cost control.
- Operational burden for key management and restore testing.
- Mitigation: automate backups, test restores regularly, and use B2 lifecycle rules to manage cost.

**Alternatives:**
- Managed backup services, other object storage providers, or a self-hosted offsite server.

---

## ADR 004 — Host OS: Raspberry Pi OS with controlled update process  
**Status:** Accepted

**Context:** Need a stable, well supported OS on Pi hardware that is lightweight and familiar.

**Decision:** Run Raspberry Pi OS (Debian derivative). Apply updates in a controlled manner: test critical updates in staging, schedule maintenance windows and document rollback procedures.

**Consequences:**
- Good hardware compatibility and predictability.
- Requires disciplined update practice and occasional manual intervention.
- Mitigation: maintain a tested image snapshot and clear upgrade/rollback documentation.

**Alternatives:**
- Rolling distributions such as Arch (more maintenance).
- Ubuntu Server (heavier, but longer upstream support in some cases).

---

## ADR 005 — Administrative access: Tailscale for mesh VPN and admin operations  
**Status:** Accepted

**Context:** Administrative tools and private services must be reachable securely without exposing them to the public Internet.

**Decision:** Use Tailscale for secure admin access and mesh networking. Restrict admin UIs to the Tailscale network.

**Consequences:**
- Simple and secure remote admin access with low latency.
- Dependency on Tailscale control plane. If it is down, convenient admin access may be impacted.
- Mitigation: document recovery options and keep a local superuser account for emergency access.

**Alternatives:**
- OpenVPN, WireGuard self-hosted, or an SSH bastion host.

---

## ADR 006 — Storage layout: external SSD mounted at `/srv` and Docker volumes for state  
**Status:** Accepted

**Context:** Require durable, easily backed up storage for user data and container state. Need separation between users.

**Decision:** Mount external SSD(s) at `/srv/hamish` and `/srv/will`. Use Docker named volumes mapped to directories on the SSD for databases and persistent application data.

**Consequences:**
- Clear separation of user data and simpler backup strategy.
- SSD remains a single point of failure on the host.
- Mitigation: SMART monitoring, frequent backups to B2 and documented replacement steps.

**Alternatives:**
- Use SD card storage (not recommended), network storage or NAS.

---

## ADR 007 — Database: local PostgreSQL container with persistent volume and scheduled dumps  
**Status:** Accepted

**Context:** Services such as Immich require a relational database. Preference for local control and offline capability.

**Decision:** Run PostgreSQL in a container with a dedicated persistent volume on the external SSD. Schedule regular logical dumps and push them to Backblaze B2 using rclone crypt.

**Consequences:**
- Local performance and full control over backups and restores.
- Need to manage upgrades and test backups.
- Mitigation: pin PostgreSQL versions for stability, document migration steps and practice restores.

**Alternatives:**
- Use a managed database service or a lightweight file DB like SQLite for trivial services.

---

## ADR 008 — Authentication strategy: service level auth and no unified SSO (for now)  
**Status:** Accepted

**Context:** Small household userbase where each service provides its own authentication. Avoid coupling services until there is clear demand.

**Decision:** Maintain per-service authentication (for example Immich accounts, FileGator basic auth). Defer introducing SSO until there is a clear operational benefit.

**Consequences:**
- Simpler, independent deployments and less operational coupling.
- Multiple credentials to manage for users.
- Mitigation: provide password manager guidance for housemates and consider SSO later if needed.

**Alternatives:**
- Deploy SSO now (Keycloak, Authelia) or use a forward-auth proxy at the reverse proxy layer.

---

## ADR 009 — Secrets management: Docker secrets and encrypted files, avoid committing secrets to repo  
**Status:** Accepted

**Context:** Secrets including DB passwords and API keys must not be stored in version control.

**Decision:** Use Docker secrets where supported. For other use cases, store secrets in an encrypted filesystem such as `gocryptfs` and reference the files from Compose. Never commit secrets to git.

**Consequences:**
- Improved security posture and reduced accidental exposure.
- Extra steps to unlock secrets on boot and to rotate keys.
- Mitigation: document unlock and rotation procedures and keep secure offsite copies of master keys.

**Alternatives:**
- Use a secret manager such as Vault (more operational overhead) or environment variables (not secure).

---

## ADR 010 — Container management UI: Portainer restricted to admin network  
**Status:** Accepted

**Context:** Occasional GUI for inspecting and managing containers is useful, but UI should not be publicly accessible.

**Decision:** Run Portainer for local container management. Restrict access to the Tailscale network and store admin credentials as Docker secrets.

**Consequences:**
- Easier local management and debugging.
- Adds an additional admin attack surface.
- Mitigation: keep Portainer off public networks, use strong credentials and audit usage.

**Alternatives:**
- CLI-only management, Cockpit, or no GUI.

---

## ADR 011 — Resource allocation policy and QoS for containers  
**Status:** Accepted

**Context:** Raspberry Pi has limited memory and CPU. Some services are bursty and can destabilise the host when not constrained.

**Decision:** Enforce resource limits in Docker Compose. Example allocations: Immich ML 2 GB, PostgreSQL 1 GB, Minecraft 2 GB, other services 512 MB each. Use CPU shares and best effort scheduling. Prioritise interactive workloads like Minecraft during gameplay.

**Consequences:**
- Reduced risk of system OOM and more predictable performance.
- Requires tuning as usage patterns change.
- Mitigation: monitor memory and CPU, set alerts for OOM and swap events, and offload heavy workloads if necessary.

**Alternatives:**
- No limits and accept potential instability, or move heavy services to different hardware.

---

## ADR 012 — ML processing for photos: on-device rather than cloud  
**Status:** Accepted

**Context:** Photo data is sensitive and should not be sent to third party ML services when avoidable.

**Decision:** Run Immich ML components locally on the Pi within resource constraints. If workload grows, consider adding an edge NPU or a dedicated processing host.

**Consequences:**
- Improved privacy and offline capability.
- Potential for higher CPU usage and slower processing.
- Mitigation: schedule ML jobs at low-load times and consider hardware upgrades for heavier workloads.

**Alternatives:**
- Use cloud ML services for speed, or disable ML features.

---

## ADR 013 — Monitoring and logging: lightweight health checks, log rotation and offsite log archive  
**Status:** Accepted

**Context:** Need basic visibility into service health and reliable log retention without running heavy monitoring stacks.

**Decision:** Use Docker healthchecks and systemd level checks for critical services. Rotate local logs with `logrotate` and archive essential logs to B2 using rclone. Use an external ping service for scheduled job alerts.

**Consequences:**
- Low overhead monitoring and offsite log retention for incident investigations.
- Not a full metrics stack; limited observability for long term capacity planning.
- Mitigation: add Prometheus and Grafana later if metric needs grow.

**Alternatives:**
- Deploy full Prometheus/Grafana stack or rely only on local logs.

---

## ADR 014 — Updates and change management: controlled upgrades, pre-upgrade snapshot and rollback plan  
**Status:** Accepted

**Context:** Single-host production means upgrades can cause outages if not managed carefully.

**Decision:** Adopt controlled upgrade procedures: take pre-upgrade snapshots where possible, test upgrades in a staging environment, schedule maintenance windows and document rollback steps. Use tagged images to simplify rollbacks.

**Consequences:**
- Safer upgrade process at the cost of extra effort.
- Requires discipline to keep staging and documentation up to date.
- Mitigation: automate pre-upgrade backups and maintain a minimal staging environment.

**Alternatives:**
- Automatic updates (faster but higher risk) or no updates (unsafe).

---

## ADR 015 — Backup and retention policy: tiered retention and lifecycle rules on B2  
**Status:** Accepted

**Context:** Photo and database backups can grow quickly and incur ongoing storage costs.

**Decision:** Implement tiered retention: daily backups for 7 days, weekly backups for 8 weeks, and monthly snapshots for 12 months. Apply lifecycle policies on Backblaze B2 to remove older data and control costs. All backups are encrypted with rclone crypt.

**Consequences:**
- Predictable storage costs and clear restore points.
- Requires monitoring and occasional policy tuning.
- Mitigation: monitor backup sizes and adjust retention as needed; test restores.

**Alternatives:**
- Longer or shorter retention windows, or no lifecycle rules.

---

## ADR 016 — Privacy and data governance: minimise external processing and document data flows  
**Status:** Accepted

**Context:** Household photos, calendars and files contain personal data. Need clear accountability and minimised exposure.

**Decision:** Keep processing local where feasible, encrypt backups, document data flows and maintain a brief access policy for housemates. Separate shared directories and enforce per-service authentication.

**Consequences:**
- Better privacy and clearer accountability.
- Requires some ongoing documentation and periodic access reviews.
- Mitigation: provide a concise README for housemates and schedule periodic access reviews.

**Alternatives:**
- Offload processing to cloud providers with associated privacy trade offs.

