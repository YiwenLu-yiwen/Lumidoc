# STP 微服务 Kubernetes 配置示例

## 使用方法

将 `service-deployment.yaml` 模板中的变量替换为具体服务的值：

```bash
# 替换模板变量生成具体服务配置
export SERVICE_NAME=auth
export SERVICE_PORT=8007
envsubst < service-deployment.yaml > auth-deployment.yaml
```

## 各服务配置参数

### 1. Auth Service
```bash
export SERVICE_NAME=auth
export SERVICE_PORT=8007
```

### 2. Chat Service  
```bash
export SERVICE_NAME=chat
export SERVICE_PORT=8001
```

### 3. File Service
```bash
export SERVICE_NAME=file
export SERVICE_PORT=8004
```

### 4. FileProc Service
```bash
export SERVICE_NAME=fileproc
export SERVICE_PORT=8005
```

### 5. Graph Service
```bash
export SERVICE_NAME=graph
export SERVICE_PORT=8003
```

### 6. LightRAG Service
```bash
export SERVICE_NAME=lightrag
export SERVICE_PORT=8006
```

### 7. LLM Service
```bash
export SERVICE_NAME=llm
export SERVICE_PORT=8080
```

### 8. Project Service
```bash
export SERVICE_NAME=project
export SERVICE_PORT=8020
```

### 9. Question Service
```bash
export SERVICE_NAME=question
export SERVICE_PORT=8002
```

### 10. Monitoring Service
```bash
export SERVICE_NAME=monitoring
export SERVICE_PORT=8008
```

### 11. Gateway Service
```bash
export SERVICE_NAME=gateway
export SERVICE_PORT=8888
```

## 批量部署脚本

```bash
#!/bin/bash
# deploy-all-services.sh

# 定义所有服务
declare -A SERVICES=(
    ["auth"]="8007"
    ["chat"]="8001"
    ["file"]="8004"
    ["fileproc"]="8005"  
    ["graph"]="8003"
    ["lightrag"]="8006"
    ["llm"]="8080"
    ["project"]="8020"
    ["question"]="8002"
    ["monitoring"]="8008"
    ["gateway"]="8888"
)

# 部署所有服务
for service in "${!SERVICES[@]}"; do
    port="${SERVICES[$service]}"
    echo "部署 $service 服务 (端口: $port)"
    
    export SERVICE_NAME=$service
    export SERVICE_PORT=$port
    
    # 生成配置文件
    envsubst < service-deployment.yaml > ${service}-deployment.yaml
    
    # 应用到集群
    kubectl apply -f ${service}-deployment.yaml
    
    echo "$service 服务部署完成"
done
```

## 健康检查验证

### 1. 检查Pod状态
```bash
kubectl get pods -n stp -l app=auth
kubectl describe pod -n stp -l app=auth
```

### 2. 检查健康检查日志
```bash
# 查看Pod事件
kubectl get events -n stp --field-selector involvedObject.name=auth-deployment-xxx

# 查看容器日志
kubectl logs -n stp -l app=auth -c auth
```

### 3. 手动测试健康检查端点
```bash
# 端口转发
kubectl port-forward -n stp service/auth-service 8007:8007

# 测试健康检查
curl http://localhost:8007/health
curl http://localhost:8007/healthz
curl http://localhost:8007/ready
curl http://localhost:8007/api/health
```

## 监控集成

### Prometheus ServiceMonitor
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: stp-services
  namespace: stp
spec:
  selector:
    matchLabels:
      app: ${SERVICE_NAME}
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
```

### Grafana Dashboard 查询
```promql
# 服务健康状态
up{job=~"stp-.*"}

# 服务响应时间
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job=~"stp-.*"}[5m]))

# 服务错误率
rate(http_requests_total{job=~"stp-.*",status=~"5.."}[5m]) / rate(http_requests_total{job=~"stp-.*"}[5m])
```

## 告警规则

```yaml
groups:
- name: stp_services
  rules:
  - alert: ServiceDown
    expr: up{job=~"stp-.*"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "STP服务 {{ $labels.job }} 下线"
      description: "服务 {{ $labels.job }} 在实例 {{ $labels.instance }} 上已下线超过1分钟"

  - alert: ServiceHighErrorRate
    expr: rate(http_requests_total{job=~"stp-.*",status=~"5.."}[5m]) / rate(http_requests_total{job=~"stp-.*"}[5m]) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "STP服务 {{ $labels.job }} 错误率过高"
      description: "服务 {{ $labels.job }} 错误率 {{ $value | humanizePercentage }} 超过10%"

  - alert: ServiceHighLatency
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job=~"stp-.*"}[5m])) > 1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "STP服务 {{ $labels.job }} 延迟过高"
      description: "服务 {{ $labels.job }} 95%分位延迟 {{ $value }}s 超过1秒"
```