# Benchmark for ack-mcp-server

## Briefing

此benchmark串联 三方AI Agent + LLM Model + ack-mcp-server，在定制的场景任务task下进行效果测试验证。  
部分case需要由三方裁判llm来进行验证(verify)。

运行结果将在 {{BENCHMARK_HOME}}/results 下记录每次运行结果报告。
文件目录结构为：

```angular2html
| - benchmarks
        | -  results
                | - 20250917-report.yaml
                | - 20250918-report.yaml
```
report内容样例：
```yaml
report_metadata:
  creationTimestamp: '2025-09-18T05:51:48Z'
  finishedTimestamp: '2025-09-18T05:51:48Z'
  ai_agent: 
    name: kubectl-ai
    version: v0.0.1
  llm_model:
    name: qwen3-coder-plus
  mcp-server:
    - name: ack-mcp-server
      version: v0.0.1
  tools:
    - ack_kubectl
    - diagnose_resource
    - get_current_time
    - get_diagnose_resource_result
    - list_clusters
    - query_audit_logs
    - query_controlplane_logs
    - query_inspect_report
    - query_prometheus
    - query_prometheus_metric_guidance
  external_configs:
    - debug: true
    - debug_log_path: /tmp/qwen-code-debug.log
results:
  tasks:
    - task_name: 1-fix-pod-oom
      is_success: true
      error: null
      startTimestamp: '2025-09-18T05:51:48Z'
      finishedTimestamp: '2025-09-18T05:51:48Z'
      result_content: xxx
      verify_content: xxx
    - task_name: 2-query-cluster-resource-usage
      is_success: true
      error: null
      startTimestamp: '2025-09-18T05:51:48Z'
      finishedTimestamp: '2025-09-18T05:51:48Z'
      result_content: xxx
      verify_content: xxx
      verify_config:                  # task的结果由另一个大模型来验证
        ai_agent:
          name: kubectl-ai
          version: v0.0.1
        llm_model:
          name: qwen3-coder-plus

```

### Support AI Agents

- [kubectl-ai](https://github.com/GoogleCloudPlatform/kubectl-ai/blob/main/pkg/mcp/README.md#local-stdio-based-server-configuration)
- [QWen Code](https://qwenlm.github.io/qwen-code-docs/zh/tools/mcp-server/#%E4%BD%BF%E7%94%A8-qwen-mcp-%E7%AE%A1%E7%90%86-mcp-%E6%9C%8D%E5%8A%A1%E5%99%A8)
- Later [Claude Code](https://docs.claude.com/zh-CN/docs/claude-code/mcp)
- Later [Cursor](https://cursor.com/cn/docs/context/mcp/directory)
- Later [Gemini CLI](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md#configure-the-mcp-server-in-settingsjson)
- Later [VS Code](https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_add-an-mcp-server)

### Support LLM Models

QWen
- qwen3-coder-plus
- qwen3-32b

Claude (Later)

Gemini (Later)

Deepseek (Later)


## How to use

### Prepare Dependencies

#### 1. Config Aliyun Account AccessKey and Run ack-mcp-server

#### 2. Need Existing Alibaba Container Service Cluster with intranet kubeconfig

Prepare the ACK cluster for testing, which needs to have at least 3 nodes with 4C8G configuration, and requires mounting a public IP (EIP) to enable public access to the kubeconfig.

Additionally, rename this cluster to include the keyword 'benchmark' in the cluster name, and ensure that the cluster with the 'benchmark' keyword remains unique within your account.

#### 3. Install AI Agent and LLM Model

#### kubectl-ai

1. install kubectl-ai CLI

2. export env
```
export OPENAI_API_KEY={{your-api-key-here}}
export OPENAI_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1/
export XDG_CONFIG_HOME={{kubectl-ai mcp server config dir path}}
# kubectl-ai will create a config file in $XDG_CONFIG_HOME/kubectl-ai/mcp.yaml
```

3. then set mcp.yaml
```angular2html
servers:
  - name: ack-mcp-server-local
    url: http://localhost:8000/mcp
```

4. finally, run kubectl-ai with mcp-client

```
kubectl-ai --llm-provider=openai --model=qwen3-coder-plus --mcp-client
```

e2e run benchmark task will  use script ```benchmarks/agents/kubectl-ai/run_prompt.sh```


#### qwen code

1. install qwen code cli

2. set env
```angular2html
export OPENAI_API_KEY="{{your-api-key-here}}"
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1/"
export OPENAI_MODEL="qwen3-32b"
```

3. add ack-mcp-server to qwen code
```angular2html
qwen mcp add --transport http ack-mcp-server http://localhost:8000/mcp --trust
```

4. run qwen code

```angular2html
qwen --openai-api-key "{{your-api-key-here}}" --openai-base-url "https://dashscope.aliyuncs.com/compatible-mode/v1/" --model "qwen3-32b" -p "帮我查询我有哪些集群，并看下行疾的集群里是否有异常的应用"
```

e2e run benchmark task will  use script ```benchmarks/agents/qwen_code/run_prompt.sh```




### E2E run benchmark task

after you prepare the dependencies, you can e2e run the benchmark.

```shell
cd {{BENCHMARK_HOME}}

# run single task
./run_benchmark.sh --openai-api-key {{your-api-key-here}} --agent qwen_code --model qwen3-coder-plus --task "history-top-resource-usage-app-analysis"

# run all tasks
./run_benchmark.sh --openai-api-key {{your-api-key-here}} --agent qwen_code --model qwen3-coder-plus

```


   
