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

## 如何构建镜像

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

## 如何运行镜像

```
docker run -e ACCESS_KEY_ID=<your-access-key-id> -e ACCESS_KEY_SECRET=<your-access-key-secret> -p 8000:8000 ack-mcp-server:1.0 python -m main_server --transport http --allow-write --host 127.0.0.1 --port 8000
```

## Host Configuration

Helm Chart 通过 `host` values 参数配置服务绑定地址，默认为 `127.0.0.1`，仅允许本地访问。如需在集群内部暴露服务，可通过 `--set host=0.0.0.0` 调整，但必须配合安全措施。

## Production Security

生产环境部署时，建议采取以下安全措施：

- **Ingress + TLS**：配合 Kubernetes Ingress Controller（如 Nginx Ingress、ALB Ingress）实现 TLS 终止，确保 HTTPS 加密传输。
- **NetworkPolicy**：使用 Kubernetes NetworkPolicy 限制 Pod 的网络访问范围，仅允许必要的流量。
- **Origin 白名单**：配置 `--allowed-origins` 参数或 `ALLOWED_ORIGINS` 环境变量，限制允许的请求来源。
- **Service Mesh**：考虑使用 Service Mesh（如 Istio）实现 mTLS 双向认证，增强服务间通信安全。

更多安全配置详见 [SECURITY.md](../SECURITY.md)。
