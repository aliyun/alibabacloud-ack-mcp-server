# 通过Helm Chart在Kubernetes集群中部署ack-mcp-server

1. 通过 helm install部署ack-mcp-server至集群中，配置 accessKey、accessKeySecret
```shell
helm install \
--set accessKeyId=<your-access-key-id> \
--set accessKeySecret=<your-access-key-secret> \
--set transport=sse \
ack-mcp-server \
./deploy/helm \
-n kube-system
```

2. 通过透出service的端口，访问ack-mcp-server 

以sse transport 为例，
可通过命令``` kubectl get --raw "/api/v1/namespaces/kube-system/services/ack-mcp-server/proxy/sse" ``` 查看mcp server是否已经启动。

3. 推荐通过为Service配置负载均衡提供外网访问，对接AI Agent 或其他系统使用。

# Docker 构建部署指南

本文档介绍如何使用 Docker 部署阿里云容器服务 MCP 服务器。

# 如何构建镜像

makefile
```
# amd64 docker build
make docker-build-amd64

# arm64 docker build
make docker-build-arm64
```

docker build command
```
# 如 linux/arm64 架构 
docker build -t ack-mcp-server:1.0 . -f ./deploy/Dockerfile --platform linux/arm64
```

# 如何运行镜像

```
docker run -e ACCESS_KEY_ID=<your-access-key-id> -e ACCESS_KEY_SECRET=<your-access-key-secret> -p 8000:8000 ack-mcp-server:1.0 python -m main_server --transport http --allow-write --host 0.0.0.0 --port 8000
```
