# Docker 部署指南

本文档介绍如何使用 Docker 部署阿里云容器服务 MCP 服务器。

# 如何构建镜像

```
# 如 linux/arm64 架构 
docker build -t ack-mcp-server:1.0 . -f ./deploy/Dockerfile --platform linux/arm64
```

# 如何运行镜像

```
docker run -e ACCESS_KEY_ID=<your-access-key-id> -e ACCESS_KEY_SECRET=<your-access-key-secret> -p 8000:8000 ack-mcp-server:1.0 python -m main_server --transport http --allow-write --host 0.0.0.0 --port 8000
```
