# Observability resources

## What we monitor and why

The goal is to know that the system is healthy and be able to diagnose fast when
it isn't.
Signals about being unhealthy can come from different layers - cluster, node,
kube api or app iteself, hence the following setup:

### Application layer
- `*_requests_total` by `status` and `*_request_duration_seconds` percentiles to
  catch user facing errors and latency spikes.
  Directly reflect user impact regardless of the root cause.
- `ml_api_predictions_total` is a functional signal:
  requests can return 200 while predictions silently stop.
  Wouldn't be caught by the error rate.
- `backend_api_db_queries_total{status}` and `backend_api_db_connections_active`
  - the DB is backend-api's only dependency, so postgres health is a likely
    cause of backend errors and the first thing to check.
- `ml_api_memory_bytes` is exposed too, but the app always reports `0`, so I
  don't rely on it.

### Kubernetes / workload layer
- `kube_pod_status_ready` - a pod can be Running but not Ready, in which case it
  serves no traffic.
- restarts + `kube_pod_container_status_waiting_reason` (CrashLoopBackOff) -
  catches crash loops and flapping.
- `kube_deployment_status_replicas_available` vs `spec_replicas` - catches a
  rollout that doesn't become healthy.
- `kube_pod_container_resource_requests/limits` - how much resources were
  allocated to the applications.

### Container resources layer
- `container_memory_working_set_bytes` vs `container_spec_memory_limit_bytes` -
  usage vs limit.
  KSM knows the limit but not the usage; cAdvisor knows the usage.
  This is the "memory vs requests/limits" view.
- CPU throttling ratio (`container_cpu_cfs_throttled_periods_total` /
  `_periods_total`) - a pod can be alive but starved.
- `container_oom_events_total` - direct evidence of memory pressure.

### Node layer
- `node_memory_MemAvailable_bytes`/`MemTotal_bytes` and
  `node_filesystem_avail_bytes`/`size_bytes` - the capacity all of the above
  consumes.

### Logs layer for diagnostics
- Metrics tell you that something is broken; logs can tell why.
  I aggregate all container logs with pod/namespace metadata and drop the 2xx
  healthcheck noise so real entries are readable.

Deliberately not monitored here
- apiserver / CoreDNS / control-plane - not exposed on k3s and not relevant to
  service health in this setup.
- KSM families beyond `pods`/`deployments`/`nodes` are not needed for the
  excercise.
- the observability stack's own metrics - a known gap, worth adding at more
  production-like environment.

## What we collect

### Metrics

| job | target | path | why |
| --- | --- | --- | --- |
| `ml-api` | `ml-api.ml-api.svc:8000` | `/metrics` | app metrics (requests, latency, predictions, memory) |
| `backend-api` | `backend-api.backend-api.svc:8000` | `/metrics` | app metrics (requests, latency, DB queries, connections) |
| `kube-state-metrics` | `vm-kube-state-metrics:8080` | `/metrics` | pod/deployment/node state |
| `node-exporter` | `vm-prometheus-node-exporter:9100` | `/metrics` | node CPU/memory/disk |
| `kubelet` | `<node>:10250` | `/metrics/cadvisor` | per-container CPU/memory |

Key series we rely on:

- **apps**:
  `*_requests_total{method,endpoint,status}`,
  `*_request_duration_seconds_bucket`, `ml_api_predictions_total`,
  `backend_api_db_queries_total{status}`, `backend_api_db_connections_active`.
- **kube-state-metrics**:
  `kube_pod_status_ready`, `kube_pod_container_status_restarts_total`,
  `kube_pod_container_status_waiting_reason`,
  `kube_pod_container_resource_requests/limits`,
  `kube_deployment_status_replicas_available/spec_replicas`,
  `kube_node_status_condition`.
- **cAdvisor**:
  `container_memory_working_set_bytes`, `container_spec_memory_limit_bytes`,
  `container_cpu_usage_seconds_total`,
  `container_cpu_cfs_throttled_periods_total`/`_periods_total`,
  `container_oom_events_total`.
- **node-exporter**:
  `node_memory_MemAvailable_bytes/MemTotal_bytes`,
  `node_filesystem_avail_bytes/size_bytes`.

KSM is intentionally limited to the `pods`, `deployments` and `nodes` collectors
- everything else is dropped at the source to cut noise.

### Logs

All container logs are collected by the OTel logs DaemonSet and enriched with
`k8s.*` fields.
Logs are stored in VictoriaLogs.
2xx `/health` + `/ready` probe access logs are dropped in the collector.

## Dashboards

One dashboard per app, provisioned as ConfigMaps picked up by the Grafana
sidecar.

**ML API**

- Request rate by endpoint
- Requests by status
- Error ratio (5xx)
- Predictions per second
- Application memory
- Request latency percentiles (p50/p95/p99)
- CPU usage
- Memory usage vs request/limit
- Deployment replicas (available vs desired)
- Pod readiness
- Application logs (VictoriaLogs)

**Backend API**

- Request rate by endpoint
- Requests by status
- Error ratio (5xx)
- DB queries per second by status
- DB query error ratio
- Active DB connections
- Request latency percentiles
- CPU usage
- Memory usage vs request/limit
- Deployment replicas (available vs desired)
- Pod readiness
- Postgres CPU usage
- Postgres memory usage vs request/limit
- Postgres availability & pod readiness
- Application logs (VictoriaLogs)

## Alerts

All rules are `VMRule` CRs, evaluated by vmalert with a 20s interval.

### Platform rules - `infrastructure/configs` (`observability` ns)

| group | alert | severity | for | catches |
| --- | --- | --- | --- | --- |
| `apps.availability` | `AppTargetDown` | critical | 2m | collector can't scrape an app/target |
| | `PodNotReady` | critical | 5m | pod not Ready |
| | `DeploymentReplicasMismatch` | critical | 10m | available < desired replicas |
| `apps.workload` | `PodCrashLooping` | critical | 5m | CrashLoopBackOff |
| | `PodRestartingFrequently` | warning | 5m | > 5 restarts/hour |
| | `ContainerOOMKilled` | warning | 1m | OOM kill in last 10m |
| | `ContainerMemoryNearLimit` | warning | 10m | working set > 90% of limit |
| | `ContainerCPUThrottling` | warning | 15m | > 25% throttled periods |
| `cluster.nodes` | `NodeNotReady` | critical | 5m | node NotReady |
| | `NodeMemoryPressure` | warning | 10m | < 10% memory available |
| | `NodeDiskPressure` | warning | 10m | < 10% disk free |
| `cluster.scrape` | `KubeletDown` | warning | 5m | kubelet unscrapeable |
| | `ClusterExporterDown` | warning | 5m | KSM / node-exporter down |

### App-scoped rules

Part of the app kustomize bundles, scoped to their namespaces:

| app | alert | severity | for |
| --- | --- | --- | --- |
| ml-api | `MLAPIHighErrorRate` (>5% 5xx) | critical | 5m |
| ml-api | `MLAPIHighLatencyP95` (>5s) | warning | 10m |
| ml-api | `MLAPINoPredictions` | warning | 10m |
| backend-api | `BackendAPIHighErrorRate` (>5% 5xx) | critical | 5m |
| backend-api | `BackendAPIHighLatencyP95` (>1s) | warning | 10m |
| backend-api | `BackendDBQueryErrors` | critical | 5m |

## Alert routing

- vmalert gets its datasource through the internal `vmauth`;
- Alertmanager routes everything to the `blackhole` receiver - alerts are
  evaluated and visible in the vmalert/Alertmanager UIs but no one is notified.
- `group_by:
  [alertname, namespace]`, `group_wait 30s`, `group_interval 5m`,
  `repeat_interval 4h`.
- Inhibition:
  `AppTargetDown` suppresses same-`job` warnings.

## Access

```sh
kubectl -n observability port-forward svc/vm-grafana      3000:80    # dashboards + explore
kubectl -n observability port-forward svc/vmsingle-vm     8428:8428  # VMUI /vmui/
kubectl -n observability port-forward svc/vlsingle-vm     9428:9428  # VictoriaLogs /select/vmui/
kubectl -n observability port-forward svc/vmalert-vm      8080:8080  # rules + active alerts
kubectl -n observability port-forward svc/vmalertmanager-vm 9093:9093 # alertmanager
```
