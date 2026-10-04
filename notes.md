# Hints and links

1. Grafana :3000, admin:admin
2. VMUI: `kubectl -n observability port-forward svc/vmsingle-vm 8428:8428`; http://localhost:8428/vmui/
3. Helm charts:
    VM kube stack - https://artifacthub.io/packages/helm/victoriametrics/victoria-metrics-k8s-stack
    VM operator - https://artifacthub.io/packages/helm/victoriametrics/victoria-metrics-operator

# Issues

1. Application container images don't have linux/amd64 builds in the registry.
    - fix: pull arm64, mount it, inspect CMD and env vars via `docker image inspect`, cp python scripts and requirements.txt from mounted containers and reimplement dockerfile to rebuild for amd64
2. High vulns in python apps.
3. Would be nice to mention GH_TOKEN and its permissions scope in the assignment. Can be copied from https://fluxcd.io/flux/installation/bootstrap/github/


# TradeOffs or What I would do differently was it prod

## Security

- Secrets of course :) 
- Root Otel DaemonSet: it runs runAsUser: 0 because kubelet writes /var/log/pods as root. I would look into a hardened options
- Proper Auth and RBAC for Grafana, VMUI, etc.
- Network policies

## Performance & Availability

- Would use cluster mode, instead of single node for  metrics and logs.
- Proper storage backend - persistent volumes + Blob storage or ElasticSearch for instance.
- Setup minimization.
- Fine-tune the logs scrape filters to reduce noise and volume.
- There's no self-scrape and no self-monitoring of the observability stack itself. It would make sense to have it in a production environment.

## QoL & Experience

- Would install otel collector operator.
- Would set proper metrics/logs retention.
- Run Grafana as a separate installation outside of the VM stack using the Grafana operator for a k8s native approach.

## TradeOffs

- It would be possible to use VM's analogue of `ServiceMonitors` - `VMServiceScrape` for metrics endpoints discovery as CRs, but that'd require to use vmagent. For Otel collector there's also an option to use `TargetAllocator` but that requires an OTel operator. I used OTel collector to make it flexible in terms of swapping the backend. With current implementation it's easier to swich VM to Prometheus or Mimir without changing the agent and scraping.
- To edit grafana dashboards in the UI and keep using sidecar approach with dashboards as CMs, one needs to hack around it a bit, because Grafana UI exports dashboards as V2 spec which is not supported by the sidecar approach. To get the V1 compatible spec it's needed to be saved as a copy dashbaord and run curl to Grafana API
```
curl -s -u admin:admin \
  http://localhost:3000/apis/dashboard.grafana.app/v1/namespaces/default/dashboards/<dashboard name> \
  | jq '.spec'
```
To list dashbaords: 
```
curl -s -u admin:admin \
  http://localhost:3000/apis/dashboard.grafana.app/v1/namespaces/default/dashboards/ | jq '.items[].metadata.name'
```
