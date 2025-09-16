

class PrometheusHandler:
    """Handler for ACK addon management operations."""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        """Initialize the ACK addon management handler.

        Args:
            server: FastMCP server instance
            allow_write: Whether to allow write operations
            settings: Configuration settings
        """
        self.server = server
        self.allow_write = settings.get("allow_write", True)
        self.settings = settings or {}

        # Register tools
        self._register_tools()

        logger.info("ACK Addon Management Handler initialized")

    def run_command(self, cmd: List[str]) -> str:
        """Run a kubectl command and return the output."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(cmd)}")
            logger.error(f"Error output: {e.stderr}")
            return f"Error: {e.stderr}"

    def _register_tools(self):
        """Register addon management related tools."""


        @self.server.tool(
            name="query_prometheus",
            description="query aliyun prometheus metric for a ACK cluster."
        )
        async def query_prometheus(
                ctx: Context,
                cluster_id: str = Field(
                    ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
                ),
                promql: str = Field(
                    ..., description="PromQL expression"
                ),
                start_time: str = Field(
                    ..., description="range start (rfc3339 or unix)"
                ),
                end_time: str = Field(
                    ..., description="range end (rfc3339 or unix)"
                ),
                step: str = Field(
                    ..., description="query step, e.g. 30s"
                )
        ) -> Dict[str, Any]:
            """执行 Prometheus 区间查询 /api/v1/query_range

            Args:
                ctx: MCP上下文，用于访问生命周期提供者
                resource_type: 资源类型，用于获取相关指标 (cluster, node, pod, namespace, )
                prometheus_endpoint: Prometheus HTTP基础端点，例如 https://example.com/api/v1/
                query_promql: PromQL表达式
                start: 查询开始时间 (rfc3339或unix格式)
                end: 查询结束时间 (rfc3339或unix格式)
                step: 查询步长，例如 30s
            """
            params = {"query": query_promql, "start": start, "end": end, "step": step}
            url = prometheus_endpoint + "/api/v1/query_range"
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()

        @self.server.tool(
            name="query_prometheus_metric_guidance",
            description="query aliyun prometheus metric guidance."
        )
        async def query_prometheus_metric_guidance(
                ctx: Context,
                resource_label: str = Field(
                    ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
                ),
                metric_category: str = Field(
                    ..., description="这个metric的指标使用场景分类：cpu / memory / network / disk "
                ),
        ) -> Dict[str, Any]:
            """执行 Prometheus 区间查询 /api/v1/query_range

            Args:
                ctx: MCP上下文，用于访问生命周期提供者
                resource_type: 资源类型，用于获取相关指标 (cluster, node, pod, namespace, )
                prometheus_endpoint: Prometheus HTTP基础端点，例如 https://example.com/api/v1/
                query_promql: PromQL表达式
                start: 查询开始时间 (rfc3339或unix格式)
                end: 查询结束时间 (rfc3339或unix格式)
                step: 查询步长，例如 30s
            """
            params = {"query": query_promql, "start": start, "end": end, "step": step}
            url = prometheus_endpoint + "/api/v1/query_range"
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()