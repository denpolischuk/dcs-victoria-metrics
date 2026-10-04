# DevOps Case Study - Observability

GitOps setup for the running case-study services plus the monitoring stack that
gives visibility into them:
metrics scraping, dashboards, alerting and log aggregation.

Runs on a local k3d cluster, reconciled by Flux CD.
The observability layer is the VictoriaMetrics k8s stack (VMSingle / VLSingle /
VMAlert / VMAlertmanager / Grafana) with the OpenTelemetry Collector as the
collection agent.

## Stack

- k3d - local Kubernetes
- Flux CD - GitOps reconciliation
- VictoriaMetrics k8s stack - metrics + logs storage/query, alerting, Grafana
- OpenTelemetry Collector - metrics scraping and log collection
- kube-state-metrics + node-exporter - cluster state and node metrics

## Layout

```
bootstrap/                    create the k3d cluster + flux bootstrap
clusters/devops-cs/           Flux entrypoint (infra-controllers, infra-configs, apps)
infrastructure/controllers/   namespace, Helm repo, VM operator (CRDs first)
infrastructure/configs/       VM stack, OTel collectors, dashboards, platform alerts
apps/                         services + app-scoped alert rules
docs/                         architecture, observability resources, tradeoffs
```

## Quick start

```sh
export GITHUB_TOKEN=<token with repo scope>
./bootstrap/bootstrap.sh https://github.com/<you>/devops-case-study main

# if the images are only available locally:
./bootstrap/bootstrap.sh --local https://github.com/<you>/devops-case-study main
```

## Access

```sh
kubectl -n observability port-forward svc/vm-grafana  3000:80    # Grafana (admin/admin)
kubectl -n observability port-forward svc/vmsingle-vm 8428:8428  # VMUI at /vmui/
kubectl -n observability port-forward svc/vlsingle-vm 9428:9428  # VictoriaLogs UI at /select/vmui/
```

## Docs

- [Architecture](docs/architecture.md)
- [Observability resources](docs/observability-resources.md)
- [Tradeoffs & what I'd do differently](docs/tradeoffs.md)
