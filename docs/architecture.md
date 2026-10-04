# Tooling

| tool | role | link |
| --- | --- | --- |
| VictoriaMetrics operator | reconciles `VM*` CRDs into workloads | https://docs.victoriametrics.com/operator/ |
| VictoriaMetrics k8s stack | VMSingle, VLSingle, VMAlert, VMAlertmanager, Grafana | https://docs.victoriametrics.com/victoriametrics-k8s-stack/ · [chart](https://artifacthub.io/packages/helm/victoriametrics/victoria-metrics-k8s-stack) |
| VMSingle | metrics store + PromQL query | https://docs.victoriametrics.com/victoriametrics/single-server-victoriametrics/ |
| VictoriaLogs (VLSingle) | logs store + LogsQL query | https://docs.victoriametrics.com/victorialogs/ |
| VMAlert | evaluates alerting/recording rules | https://docs.victoriametrics.com/victoriametrics/vmalert/ |
| VMAlertmanager | de-dupes/groups/routes alerts | https://docs.victoriametrics.com/victoriametrics/vmalertmanager/ |
| Grafana | dashboards + explore (metrics & logs) | https://grafana.com/docs/grafana/latest/ |
| OpenTelemetry Collector | scrape metrics, collect logs, export | https://opentelemetry.io/docs/collector/ |
| kube-state-metrics | k8s object state (pods, deployments, restarts, requests/limits) | https://github.com/kubernetes/kube-state-metrics |
| node-exporter | node CPU/memory/filesystem | https://github.com/prometheus/node_exporter |
| kubelet / cAdvisor | per-container CPU/memory | https://kubernetes.io/docs/concepts/cluster-administration/system-metrics/ |


Splitting controllers from configs is deliberate:
the operator (and its CRDs) must be installed before `VMSingle`/`VMRule`/etc.
can be created.
`dependsOn` + `wait:
true` enforces the ordering.

## Components

`infrastructure/controllers`
- `namespace` observability)
- `HelmRepository` VictoriaMetrics
- `HelmRelease` victoria-metrics-operator

`infrastructure/configs`
- `victoria-metrics-k8s-stack` HelmRelease (`releaseName:
  vm`):
  - `vmsingle` (metrics, 7d, 2Gi PVC), `vlsingle` (logs, 7d, 2Gi PVC)
  - `vmalert` + `alertmanager` (routing to a `blackhole` receiver - see alerts
    doc)
  - Grafana (with the VictoriaLogs datasource plugin; `preferred_api_version:
    dashboard.grafana.app/v1` so the sidecar-compatible dashboard spec is
    exported)
  - `kube-state-metrics` (only `pods`, `deployments`, `nodes` collectors),
    `node-exporter`
  - `vmagent` disabled - metrics come from the OTel collector
- `otel-collector` (Deployment):
  scrapes apps + KSM + node-exporter + kubelet/cAdvisor, remote-writes to
  VMSingle.
- `otel-collector-logs` (DaemonSet):
  tails `/var/log/pods`, enriches, filters, exports OTLP to VictoriaLogs.
- Dashboards (ConfigMaps, Grafana sidecar) and platform `VMRule`s.

`apps`
- Service manifests + app-scoped `VMRule`s (in each app's namespace).


# Alternative implementation

`main` uses the OTel Collector.
The branch `feat/use-vmagent` does the same with the VictoriaMetrics-native
agents (`vmagent` for metrics, `vlagent` for logs).
See [tradeoffs](tradeoffs.md) for the comparison.
