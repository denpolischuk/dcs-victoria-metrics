# Issues

1. Application container images don't have linux/amd64 builds in the registry.
    - fix: pull arm64, mount it, inspect CMD and env vars via `docker image inspect`, cp python scripts and requirements.txt from mounted containers and reimplement dockerfile to rebuild for amd64
2. 
