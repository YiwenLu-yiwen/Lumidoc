# STP项目部署指南

本文档提供STP项目在Kubernetes环境中的部署说明。

## 部署文件结构

- `auth-service.yaml`: 用户认证服务部署配置
- 其他服务配置文件将陆续添加

## 环境要求

- Kubernetes 1.19+
- kubectl 1.19+
- 已配置数据库和Redis服务

## 前置条件

### 创建配置映射

```bash
kubectl create configmap stp-config \
  --from-literal=db_host=postgres \
  --from-literal=db_port=5432 \
  --from-literal=auth_db_name=auth_db \
  --from-literal=redis_host=redis \
  --from-literal=redis_port=6379
```

### 创建密钥

```bash
kubectl create secret generic stp-db-credentials \
  --from-literal=username=stp_user \
  --from-literal=password=your_password_here
```

## 部署服务

部署用户认证服务:

```bash
kubectl apply -f auth-service.yaml
```

## 健康检查

STP所有服务均实现了健康检查接口：
- `/health`: 详细的健康状态检查，包含服务依赖状态
- `/healthz`: Kubernetes标准健康检查接口（即将实现）

## 服务扩缩容

```bash
kubectl scale deployment auth-service --replicas=3
```

## 监控与日志

所有服务日志使用结构化JSON格式输出，可被Elasticsearch-Fluentd-Kibana (EFK)堆栈收集。 