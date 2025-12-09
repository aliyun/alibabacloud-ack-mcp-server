#!/usr/bin/env bash

# 使用说明函数
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --openai-api-key KEY     OpenAI API 密钥 (必需)"
    echo "  --openai-base-url URL    OpenAI 基础 URL (默认: https://dashscope.aliyuncs.com/compatible-mode/v1/)"
    echo "  --model MODEL           模型名称 (默认: qwen3-coder-plus)"
    echo "  --prompt PROMPT         提示词 (必需)"
    echo "  -h, --help              显示此帮助信息"
    exit 1
}

# 初始化变量（设置默认值）
OPENAI_API_KEY=""
OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1/"
MODEL="qwen3-coder-plus"
PROMPT=""

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
        --prompt)
            PROMPT="$2"
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

# OPENAI_BASE_URL 和 MODEL 有默认值，不需要检查

if [ -z "$PROMPT" ]; then
    echo "错误: 缺少必需的参数 --prompt"
    usage
fi

# 执行 qwen code 命令
qwen --debug=true --openai-api-key "$OPENAI_API_KEY" --openai-base-url "$OPENAI_BASE_URL" --model "$MODEL" -p "$PROMPT"