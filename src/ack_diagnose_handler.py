



class DiagnoseHandler:
    """Handler for ACK diagnose operations."""

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

        # Cluster Diagnosis Tools
        @self.server.tool(
            name="invoke_diagnose_resource_task",
            description="Create a cluster diagnosis task for ACK cluster"
        )
        async def invoke_diagnose_resource_task(
                ctx: Context,
                resource_type: str = Field(
                    ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
                ),
                cluster_id: str,
                diagnosis_type: Optional[str] = "cluster",
                target: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            """Create cluster diagnosis task.

            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_id: Target cluster ID
                diagnosis_type: Type of diagnosis (node, ingress, cluster, memory, pod, service, network)
                target: Target specification for diagnosis

            Returns:
                Diagnosis task creation result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}

            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")

                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}

            try:
                request = cs20151215_models.CreateClusterDiagnosisRequest(
                    type=diagnosis_type,
                    target=target
                )
                runtime = util_models.RuntimeOptions()
                headers = {}

                response = await cs_client.create_cluster_diagnosis_with_options_async(
                    cluster_id, request, headers, runtime
                )

                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}

                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": getattr(response.body, 'diagnosis_id', None) if response.body else None,
                    "status": "created",
                    "type": diagnosis_type,
                    "created_time": getattr(response.body, 'created_time', None) if response.body else None,
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }

            except Exception as e:
                logger.error(f"Failed to create cluster diagnosis: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }