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

## Performance & Availability

- Would use cluster mode, instead of single node for  metrics and logs.
- Setup minimization.
- Fine-tune the logs scrape filters to reduce noise and volume.

## QoL & Experience

- Would install otel collector operator.
- Would set proper metrics/logs retention 

