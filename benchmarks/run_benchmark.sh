
#!/usr/bin/env bash

# 使用说明函数
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --openai-api-key KEY     OpenAI API 密钥 (必需)"
    echo "  --agent AGENT           运行Benchmark的AI Agent, 默认为 qwen_code, 可选为 qwen_code, kubectl-ai"
    echo "  --model MODEL           模型名称 (默认: qwen3-coder-plus)"
    echo "  --openai-base-url URL    OpenAI 基础 URL (默认: https://dashscope.aliyuncs.com/compatible-mode/v1/)"
    echo "  --task TASK_NAME        指定要运行的任务名称 (可选，不指定则运行所有任务，task.yaml中定义的task name)"
    echo "  -h, --help              显示此帮助信息"
    exit 1
}

# 初始化变量（设置默认值）
AGENT="qwen_code"
OPENAI_API_KEY=""
OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1/"
MODEL="qwen3-coder-plus"
TASK_NAME=""
BENCHMARK_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$BENCHMARK_HOME/results"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --openai-api-key)
            OPENAI_API_KEY="$2"
            shift 2
            ;;
        --openai-base-url)
            OPENAI_BASE_URL="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --agent)
            AGENT="$2"
            shift 2
            ;;
        --task)
            TASK_NAME="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "未知参数: $1"
            usage
            ;;
    esac
done

# 检查必需参数
if [ -z "$OPENAI_API_KEY" ]; then
    echo "错误: 缺少必需的参数 --openai-api-key"
    usage
fi

# 检查 agent 是否有效
if [[ "$AGENT" != "qwen_code" && "$AGENT" != "kubectl-ai" ]]; then
    echo "错误: 无效的 agent '$AGENT'，只支持 qwen_code 或 kubectl-ai"
    usage
fi

# 创建结果目录
mkdir -p "$RESULTS_DIR"

# 生成报告文件名
TIMESTAMP=$(date '+%Y%m%d-%H-%M')
RANDOM_STR=$(openssl rand -hex 3)
REPORT_FILE="$RESULTS_DIR/${TIMESTAMP}-${RANDOM_STR}-report.yaml"

# 记录开始时间
START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# 获取当前工程的 git commit ID
GIT_COMMIT_ID=$(cd "$BENCHMARK_HOME/.." && git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# 获取 agent 版本信息
AGENT_VERSION="unknown"
AGENT_VERSION_SCRIPT="$BENCHMARK_HOME/agents/$AGENT/version.sh"
if [ -f "$AGENT_VERSION_SCRIPT" ]; then
    AGENT_VERSION=$(bash "$AGENT_VERSION_SCRIPT" 2>/dev/null | head -1 | tr -d '\n' || echo "unknown")
fi

echo "开始执行 benchmark..."
echo "Agent: $AGENT"
echo "Agent Version: $AGENT_VERSION"
echo "Model: $MODEL"
echo "Git Commit ID: $GIT_COMMIT_ID"
if [ -n "$TASK_NAME" ]; then
    echo "指定任务: $TASK_NAME"
else
    echo "运行模式: 所有任务"
fi
echo "结果将保存到: $REPORT_FILE"

# 初始化报告文件
cat > "$REPORT_FILE" << EOF
report_metadata:
  creationTimestamp: '$START_TIME'
  finishedTimestamp: ''
  ai_agent: 
    name: $AGENT
    version: $AGENT_VERSION
  llm_model:
    name: $MODEL
  mcp-server:
    - name: ack-mcp-server
      version: $GIT_COMMIT_ID
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
    - debug_log_path: /tmp/$AGENT-debug.log
results:
  tasks:
EOF

# 函数：执行脚本并捕获输出
execute_script() {
    local script_path="$1"
    local script_name="$2"
    local output_file="$3"
    
    echo "执行 $script_name: $script_path"
    echo "----------------------------------------"
    
    if [ ! -f "$script_path" ]; then
        echo "警告: 脚本文件不存在: $script_path"
        return 1
    fi
    
    # 执行脚本并同时输出到 stdout 和文件
    if bash "$script_path" 2>&1 | tee "$output_file"; then
        echo "----------------------------------------"
        echo "✓ $script_name 执行成功"
        return 0
    else
        echo "----------------------------------------"
        echo "✗ $script_name 执行失败"
        return 1
    fi
}

# 函数：执行 AI Agent
execute_ai_agent() {
    local prompt="$1"
    local output_file="$2"
    local agent_script="$BENCHMARK_HOME/agents/$AGENT/run_prompt.sh"
    
    echo "执行 AI Agent: $AGENT"
    echo "Prompt: $prompt"
    echo "----------------------------------------"
    
    if [ ! -f "$agent_script" ]; then
        echo "错误: Agent 脚本不存在: $agent_script"
        return 1
    fi
    
    # 执行 AI Agent 脚本，同时输出到 stdout 和文件
    if bash "$agent_script" \
        --openai-api-key "$OPENAI_API_KEY" \
        --openai-base-url "$OPENAI_BASE_URL" \
        --model "$MODEL" \
        --prompt "$prompt" 2>&1 | tee "$output_file"; then
        echo "----------------------------------------"
        echo "✓ AI Agent 执行成功"
        return 0
    else
        echo "----------------------------------------"
        echo "✗ AI Agent 执行失败"
        return 1
    fi
}

# 函数：执行 AI Agent 验证
execute_ai_agent_verify() {
    local verify_prompt="$1"
    local agent_result="$2"
    local output_file="$3"
    local detailed_output_file="$4"  # 新增：用于保存详细过程的文件
    
    # 确定使用的 agent 和 model
    local verify_agent="$AGENT"
    local verify_model="$MODEL"
    local verify_agent_script=""
    
    # 如果 task.yaml 中指定了 verify 配置，则使用指定的配置
    if [ -n "$VERIFY_AI_AGENT_NAME" ]; then
        verify_agent="$VERIFY_AI_AGENT_NAME"
    fi
    
    if [ -n "$VERIFY_LLM_MODEL" ]; then
        verify_model="$VERIFY_LLM_MODEL"
    fi
    
    # 确定 agent 脚本路径
    verify_agent_script="$BENCHMARK_HOME/agents/$verify_agent/run_prompt.sh"
    
    # 拼接 AI Agent 结果和验证 prompt
    local combined_prompt="验证问题：\n $verify_prompt \n\n 以下是AI的回答结果：\n\n$agent_result\n\n"
    
    # 记录验证过程的详细信息到 detailed_output_file
    cat > "$detailed_output_file" << EOF
==========================================
AI验证过程详细记录
==========================================
验证代理: $verify_agent
使用模型: $verify_model
==========================================
原始验证任务Prompt:
$verify_prompt
==========================================
传递给验证AI的完整Prompt:
$combined_prompt
==========================================
验证AI的输出结果:
EOF
    
    echo ""
    echo "==========================================="
    echo "执行 AI Agent 验证: $verify_agent"
    echo "使用模型: $verify_model"
    echo "==========================================="
    echo "验证任务 Prompt: $verify_prompt"
    echo "==========================================="
    echo "最终验证 Prompt: $combined_prompt"
    echo "----------------------------------------"
    
    if [ ! -f "$verify_agent_script" ]; then
        echo "错误: Agent 脚本不存在: $verify_agent_script"
        echo "错误: Agent 脚本不存在: $verify_agent_script" >> "$detailed_output_file"
        return 1
    fi
    
    echo "开始执行 AI 验证..."
    echo "----------------------------------------"
    
    # 构建完整的bash命令并输出到stdout
    local full_command="bash \"$verify_agent_script\" --openai-api-key \"$OPENAI_API_KEY\" --openai-base-url \"$OPENAI_BASE_URL\" --model \"$verify_model\" --prompt \"$combined_prompt\""
    echo "完整执行命令:"
    echo "$full_command"
    echo "----------------------------------------"
    
    # 执行 AI Agent 脚本，同时输出到 stdout、原输出文件和详细输出文件
    if bash "$verify_agent_script" \
        --openai-api-key "$OPENAI_API_KEY" \
        --openai-base-url "$OPENAI_BASE_URL" \
        --model "$verify_model" \
        --prompt "$combined_prompt" 2>&1 | tee -a "$detailed_output_file" | tee "$output_file"; then
        echo "----------------------------------------"
        echo "✓ AI Agent 验证执行成功"
        echo "=========================================="
        echo "=========================================" >> "$detailed_output_file"
        echo "验证执行状态: 成功" >> "$detailed_output_file"
        echo "=========================================" >> "$detailed_output_file"
        return 0
    else
        echo "----------------------------------------"
        echo "✗ AI Agent 验证执行失败"
        echo "=========================================="
        echo "=========================================" >> "$detailed_output_file"
        echo "验证执行状态: 失败" >> "$detailed_output_file"
        echo "=========================================" >> "$detailed_output_file"
        return 1
    fi
}

# 函数：解析 task.yaml 文件
parse_task_yaml() {
    local task_dir="$1"
    local task_yaml="$task_dir/task.yaml"
    
    if [ ! -f "$task_yaml" ]; then
        echo "错误: task.yaml 不存在: $task_yaml"
        return 1
    fi
    
    # 解析主 prompt (在 scripts 部分)
    TASK_NAME=$(grep "task_name:" "$task_yaml" | sed 's/.*task_name: *"\([^"]*\)".*/\1/')
    PROMPT=$(awk '/scripts:/,/verify:/ {if ($0 ~ /[[:space:]]*prompt:/) {gsub(/.*prompt: *"/, ""); gsub(/".*/, ""); print; exit}}' "$task_yaml")
    SETUP_SCRIPT=$(grep "setup_script_file:" "$task_yaml" | sed 's/.*setup_script_file: *"\([^"]*\)".*/\1/')
    CLEANUP_SCRIPT=$(grep "cleanup_script_file:" "$task_yaml" | sed 's/.*cleanup_script_file: *"\([^"]*\)".*/\1/')
    VERIFY_SCRIPT=$(grep "verify_script_file:" "$task_yaml" | sed 's/.*verify_script_file: *"\([^"]*\)".*/\1/')
    
    # 检查是否有 verify 配置
    if grep -q "verify:" "$task_yaml"; then
        # 解析验证用的提示词 (注意 YAML 结构)
        VERIFY_PROMPT=$(grep -A 3 "verify:" "$task_yaml" | grep "prompt:" | sed 's/.*prompt: *"\([^"]*\)".*/\1/' | head -1)
        
        # 解析 verify_config 信息
        VERIFY_AI_AGENT_NAME=$(grep -A 8 "verify:" "$task_yaml" | grep -A 3 "ai_agent:" | grep "name:" | sed 's/.*name: *\([^ ]*\).*/\1/' | head -1)
        VERIFY_AI_AGENT_VERSION=$(grep -A 8 "verify:" "$task_yaml" | grep -A 3 "ai_agent:" | grep "version:" | sed 's/.*version: *\([^ ]*\).*/\1/' | head -1)
        VERIFY_LLM_MODEL=$(grep -A 8 "verify:" "$task_yaml" | grep -A 3 "llm_model:" | grep "name:" | sed 's/.*name: *\([^ ]*\).*/\1/' | head -1)
    else
        VERIFY_PROMPT=""
        VERIFY_AI_AGENT_NAME=""
        VERIFY_AI_AGENT_VERSION=""
        VERIFY_LLM_MODEL=""
    fi
    
    echo "解析任务: $TASK_NAME"
    echo "Prompt: $PROMPT"
    echo "Setup: $SETUP_SCRIPT"
    echo "Cleanup: $CLEANUP_SCRIPT"
    echo "Verify: $VERIFY_SCRIPT"
    if [ -n "$VERIFY_PROMPT" ]; then
        echo "Verify Prompt: $VERIFY_PROMPT"
        echo "Verify AI Agent: $VERIFY_AI_AGENT_NAME $VERIFY_AI_AGENT_VERSION"
        echo "Verify LLM Model: $VERIFY_LLM_MODEL"
    fi
}

# 函数：执行单个任务
execute_task() {
    local task_dir="$1"
    local task_name=$(basename "$task_dir")
    
    echo ""
    echo "=========================================="
    echo "执行任务: $task_name"
    echo "=========================================="
    
    # 解析 task.yaml
    parse_task_yaml "$task_dir"
    
    if [ -z "$TASK_NAME" ] || [ -z "$PROMPT" ]; then
        echo "错误: 无法解析 task.yaml 文件"
        return 1
    fi
    
    # 创建临时目录存储输出
    local temp_dir=$(mktemp -d)
    local setup_output="$temp_dir/setup_output.txt"
    local agent_output="$temp_dir/agent_output.txt"
    local verify_output="$temp_dir/verify_output.txt"
    local verify_ai_output="$temp_dir/verify_ai_output.txt"
    local verify_ai_detailed_output="$temp_dir/verify_ai_detailed_output.txt"  # 新增：详细验证过程文件
    local cleanup_output="$temp_dir/cleanup_output.txt"
    
    local task_start_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local task_success=true
    local task_error=""
    
    # 1. 执行 setup
    if [ -n "$SETUP_SCRIPT" ]; then
        if ! execute_script "$task_dir/$SETUP_SCRIPT" "setup" "$setup_output"; then
            task_success=false
            task_error="setup 执行失败"
        fi
    fi
    
    # 2. 执行 AI Agent
    if [ "$task_success" = true ]; then
        if ! execute_ai_agent "$PROMPT" "$agent_output"; then
            task_success=false
            task_error="AI Agent 执行失败"
        fi
    fi
    
    # 3. 执行 verify
    local verify_success=true
    if [ "$task_success" = true ] && [ -n "$VERIFY_SCRIPT" ]; then
        if ! execute_script "$task_dir/$VERIFY_SCRIPT" "verify" "$verify_output"; then
            verify_success=false
            task_error="verify 执行失败"
        fi
    fi
    
    # 4. 执行 AI 验证（如果有 verify prompt）
    local verify_ai_success=true
    local verify_ai_result=""
    if [ "$task_success" = true ] && [ -n "$VERIFY_PROMPT" ]; then
        # 读取 AI Agent 的结果
        local agent_result=""
        if [ -f "$agent_output" ]; then
            agent_result=$(cat "$agent_output")
        fi
        
        if ! execute_ai_agent_verify "$VERIFY_PROMPT" "$agent_result" "$verify_ai_output" "$verify_ai_detailed_output"; then
            verify_ai_success=false
            task_error="AI 验证执行失败"
        else
            # 读取 AI 验证的详细过程（包含完整过程和结果）
            if [ -f "$verify_ai_detailed_output" ]; then
                verify_ai_result=$(cat "$verify_ai_detailed_output" | sed 's/"/\\"/g' | tr '\n' ' ')
            fi
        fi
    fi
    
    # 5. 执行 cleanup
    if [ -n "$CLEANUP_SCRIPT" ]; then
        execute_script "$task_dir/$CLEANUP_SCRIPT" "cleanup" "$cleanup_output"
    fi
    
    local task_end_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # 读取输出内容
    local result_content=""
    local verify_content=""
    
    if [ -f "$agent_output" ]; then
        result_content=$(cat "$agent_output" | sed 's/"/\\"/g' | tr '\n' ' ')
    fi
    
    # 合并传统验证和 AI 验证结果
    if [ -f "$verify_output" ]; then
        verify_content=$(cat "$verify_output" | sed 's/"/\\"/g' | tr '\n' ' ')
    fi
    
    # 如果有 AI 验证结果，则将完整的验证过程添加到 verify_content 中
    if [ -n "$verify_ai_result" ]; then
        if [ -n "$verify_content" ]; then
            verify_content="$verify_content $verify_ai_result"
        else
            verify_content="$verify_ai_result"
        fi
    fi
    
    # 添加任务结果到报告
    if [ -n "$VERIFY_PROMPT" ]; then
        # 如果有 AI 验证配置，添加 verify_config 部分
        # 确定报告中使用的 agent 和 model 名称
        local report_agent_name="$AGENT"
        local report_agent_version="$AGENT_VERSION"
        local report_model_name="$MODEL"
        
        # 如果 task.yaml 中指定了 verify 配置，则使用指定的配置
        if [ -n "$VERIFY_AI_AGENT_NAME" ]; then
            report_agent_name="$VERIFY_AI_AGENT_NAME"
        fi
        if [ -n "$VERIFY_AI_AGENT_VERSION" ]; then
            report_agent_version="$VERIFY_AI_AGENT_VERSION"
        fi
        if [ -n "$VERIFY_LLM_MODEL" ]; then
            report_model_name="$VERIFY_LLM_MODEL"
        fi
        
        cat >> "$REPORT_FILE" << EOF
    - task_name: $task_name
      is_success: $task_success
      error: $([ "$task_success" = true ] && echo "null" || echo "\"$task_error\"")
      startTimestamp: '$task_start_time'
      finishedTimestamp: '$task_end_time'
      result_content: "$result_content"
      verify_content: "$verify_content"
      verify_config:
        ai_agent:
          name: $report_agent_name
          version: $report_agent_version
        llm_model:
          name: $report_model_name
EOF
    else
        # 没有 AI 验证配置的标准格式
        cat >> "$REPORT_FILE" << EOF
    - task_name: $task_name
      is_success: $task_success
      error: $([ "$task_success" = true ] && echo "null" || echo "\"$task_error\"")
      startTimestamp: '$task_start_time'
      finishedTimestamp: '$task_end_time'
      result_content: "$result_content"
      verify_content: "$verify_content"
EOF
    fi
    
    # 清理临时文件
    rm -rf "$temp_dir"
    
    if [ "$task_success" = true ]; then
        echo "✓ 任务 $task_name 执行成功"
    else
        echo "✗ 任务 $task_name 执行失败: $task_error"
    fi
    
    return $([ "$task_success" = true ] && echo 0 || echo 1)
}

# 主执行逻辑
echo ""
echo "开始遍历 tasks 目录..."

TASKS_DIR="$BENCHMARK_HOME/tasks"
TASK_COUNT=0
SUCCESS_COUNT=0

# 如果指定了任务名称，只运行该任务
if [ -n "$TASK_NAME" ]; then
    # 查找指定的任务目录
    TASK_DIR=""
    for task_dir in "$TASKS_DIR"/*; do
        if [ -d "$task_dir" ]; then
            task_basename=$(basename "$task_dir")
            if [[ "$task_basename" == *"$TASK_NAME"* ]]; then
                TASK_DIR="$task_dir"
                break
            fi
        fi
    done
    
    if [ -z "$TASK_DIR" ]; then
        echo "错误: 找不到任务 '$TASK_NAME'"
        echo "可用的任务:"
        for task_dir in "$TASKS_DIR"/*; do
            if [ -d "$task_dir" ]; then
                echo "  - $(basename "$task_dir")"
            fi
        done
        exit 1
    fi
    
    echo "运行指定任务: $(basename "$TASK_DIR")"
    TASK_COUNT=1
    if execute_task "$TASK_DIR"; then
        SUCCESS_COUNT=1
    fi
else
    # 遍历 tasks 目录下的所有子目录
    for task_dir in "$TASKS_DIR"/*; do
        if [ -d "$task_dir" ]; then
            TASK_COUNT=$((TASK_COUNT + 1))
            if execute_task "$task_dir"; then
                SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
            fi
        fi
    done
fi

# 更新报告完成时间
END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
sed -i.bak "s/finishedTimestamp: ''/finishedTimestamp: '$END_TIME'/" "$REPORT_FILE"
rm -f "$REPORT_FILE.bak"

echo ""
echo "=========================================="
echo "Benchmark 执行完成"
echo "=========================================="
echo "总任务数: $TASK_COUNT"
echo "成功任务数: $SUCCESS_COUNT"
echo "失败任务数: $((TASK_COUNT - SUCCESS_COUNT))"
echo "结果报告: $REPORT_FILE"
echo "开始时间: $START_TIME"
echo "结束时间: $END_TIME"

if [ $SUCCESS_COUNT -eq $TASK_COUNT ]; then
    echo "🎉 所有任务执行成功！"
    exit 0
else
    echo "⚠️  部分任务执行失败，请查看报告了解详情"
    exit 1
fi