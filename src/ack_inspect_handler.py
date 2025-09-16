


class InspectHandler:
    """Handler for ACK inspect report operations."""

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
            name="get_cluster_inspection_result",
            description="Get cluster inspection result"
        )
        async def get_cluster_inspection_result(
                ctx: Context,
                cluster_id: str = Field(
                    ..., description='ACK ClusterId'
                ),
        ) -> Dict[str, Any]:
            """Get cluster inspection result.

            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_id: Target cluster ID
                inspection_id: Inspection task ID

            Returns:
                Inspection result
            """
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
                request = cs20151215_models.ListClusterInspectReportsRequest(
                    next_token=next_token,
                    max_results=max_results
                )
                runtime = util_models.RuntimeOptions()
                headers = {}

                response = await cs_client.list_cluster_inspect_reports_with_options_async(
                    cluster_id, request, headers, runtime
                )

                response.body.total_count
                ## TODO https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/developer-reference/api-cs-2015-12-15-listclusterinspectreports?spm=a2c4g.11186623.help-menu-85222.d_5_2_3_7_7.695437828m2twC


            except Exception as e:
                logger.error(f"Failed to list cluster inspect reports: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }

            ## if get

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
                request = cs20151215_models.GetClusterInspectionResultRequest()
                runtime = util_models.RuntimeOptions()
                headers = {}

                response = await cs_client.get_cluster_inspection_result_with_options_async(
                    cluster_id, inspection_id, request, headers, runtime
                )

                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}

                return {
                    "cluster_id": cluster_id,
                    "inspection_id": inspection_id,
                    "status": getattr(response.body, 'status', None) if response.body else None,
                    "code": getattr(response.body, 'code', None) if response.body else None,
                    "message": getattr(response.body, 'message', None) if response.body else None,
                    "result": _serialize_sdk_object(getattr(response.body, 'result', None)) if response.body else None,
                    "created": getattr(response.body, 'created', None) if response.body else None,
                    "finished": getattr(response.body, 'finished', None) if response.body else None,
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }

            except Exception as e:
                logger.error(f"Failed to get cluster inspection result: {e}")
                return {
                    "cluster_id": cluster_id,
                    "inspection_id": inspection_id,
                    "error": str(e),
                    "status": "error"
                }