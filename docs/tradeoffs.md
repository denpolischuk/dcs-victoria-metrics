# Tradeoffs & what I'd do differently

## Two implementations

There are 2 versiopns of the collection layer implementation:

- `main` - OpenTelemetry collector is used.
  A metrics Deployment and a logs DaemonSet.
  It's flexible in terms of backend.
  I can point the same agent at Prometheus/Mimir (or another OTLP endpoint)
  without changing how apps are scraped.
- `feat/use-vmagent` - VictoriaMetrics-native agents.
  `vmagent` consumes `VMServiceScrape`/`VMNodeScrape` CRs (the chart generates
  them for KSM/node-exporter/kubelet automatically, so less YAML, no
  hand-written static targets, lower resource use) and `vlagent` collects logs.

They're both GitOps and both end up in the same VMSingle/VLSingle.
The reasons I kept OTel on `main`:

- Backend portability - swapping VM for Prometheus/Mimir is an exporter change,
  not a rewrite of the discovery layer.
- Content filtering - OTel can drop log records by content (2xx healthcheck
  logs).
  `vlagent`'s `excludeFilter` is metadata-only, and VictoriaLogs has no
  message-based ingestion filter.
- The costs:
  more config/code (ConfigMap hashing for hot-reload, hand-written scrape jobs,
  kubelet RBAC), and it's an extra non-VM component.

The `vmagent` route is a smaller and more out-of-the-box solution, but lacks
features and versatility in comparison to OTel.
It, however, is more CR native, but almost the same can be eventually reached
with OTel operator if needed.
For the purpose of this task I decided to run standalone OTel collector
installations instead of running the operator.

## Security

- **Secrets** - Grafana admin password is committed as `admin`, and so is
  everything else.
  Would use `existingSecret`/SOPS/SealedSecrets.
- **Root OTel logs DaemonSet** - it runs `runAsUser:
  0` because kubelet writes `/var/log/pods` as root.
  Would look into a hardened alternative.
- **Auth & RBAC** for Grafana, VMUI, VictoriaLogs - currently only port-forward,
  no auth.
- **NetworkPolicies** - none.

## Performance & availability

- Would use cluster mode instead of single-node for metrics and logs.
- Proper storage backend - persistent volumes + blob storage for backups instead
  of a small local-path PVC.
- Fine-tune log filters - reduce noise and volume further than just healthcheck
  probes on the ingestion level.
  Usually it's often a good idea to add PII data filters such as IBANs, emails,
  phone numbers to not leak them into log indexes.
- No self-monitoring - in the OTel implementation nothing scrapes the
  observability stack itself
  (VMSingle/VLSingle/VMAlert/Alertmanager/collectors).
  Prod would want alerts on the monitoring stack too.

## QoL & experience

- Would install the OTel Collector operator (CRD-based collector + target
  allocator, auto config reload).
  That'd help to move to more CR native approach and keep observability logic
  closer to app CR bundles, like it's done with the VMRUles.
- Would set proper metrics/logs retention beyond 7d with cold storage backups
  for critical logs.
- Would run Grafana as a separate install (or via the Grafana operator) instead
  of inside the VM stack, for a more CRD-native approach.

## Other tradeoffs

- Discovery CRs vs static targets - the VM analogue of `ServiceMonitor` is
  `VMServiceScrape`, but it requires `vmagent`.
  For OTel there's the `TargetAllocator`, but that requires the OTel operator.
  I chose OTel static scrape configs to keep the agent swappable.
- Dashboard editing round-trip - the Grafana UI exports dashboards as V2 specs,
  which the sidecar (ConfigMap) approach does not consume.
  To keep editing in the UI and stay on sidecars, export the V1 spec via the API
  and paste it into the ConfigMap:
  ```sh
  curl -s -u admin:admin \
    http://localhost:3000/apis/dashboard.grafana.app/v1/namespaces/default/dashboards/<name> | jq '.spec'
  # list:
  curl -s -u admin:admin \
    http://localhost:3000/apis/dashboard.grafana.app/v1/namespaces/default/dashboards/ | jq '.items[].metadata.name'
  ```
  `preferred_api_version:
  dashboard.grafana.app/v1` is set in the grafana.ini so that Grafana prefers
  the classic-backed API.
- App rules live with the apps - app alerting rules are in
  `apps/<name>/vmrules.yaml` (namespace of the app) so ownership travels with
  the service; platform/cluster rules stay in `infrastructure/configs`.

## Assignment issues & suggestions

1. Application container images have no `linux/amd64` builds in the registry.
   - How did I fix this:
     pulled the arm64 image, mounted it, inspected `CMD` and env via `docker
     image inspect`, copied `python` scripts + `requirements.txt` from the
     mounted container and reimplemented the Dockerfile for amd64.

     If it was some compiled binaries without source code, I'd be stuck there,
     hopefully it was only python scripts. 
2. High vulnerabilities in the Python app dependencies.
3. The assignment should mention the `GITHUB_TOKEN` as a requirement and its
   permissions scope (see
   https://fluxcd.io/flux/installation/bootstrap/github/).
