class KubectlHandler:
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
            name="kubectl",
            description="Kubectl tool for cluster."
        )
        async def kubectl(
                ctx: Context,
                command: str = Field(
                    ..., description='kubectl full command, e.g. kubectl get pods, need input command: get pods'
                ),
        ) -> Dict[str, Any]:
            """ Kubectl command line tool.

            Args:
                ctx: FastMCP context containing lifespan providers
                command: kubectl full command, e.g. kubectl get pods, need input command: get pods'

            Returns:
                Brief cluster list with fields: name, cluster_id, state, region_id, node_count, cluster_type
            """
            # Get base config for AK
            try:
                cmd = ["kubectl", command]
                result = self.run_command(cmd)

                # Reload kubernetes config after switching context
                config.load_kube_config()
                self.core_v1 = client.CoreV1Api()
                self.apps_v1 = client.AppsV1Api()
                self.networking_v1 = client.NetworkingV1Api()

                return {
                    "status": "success",
                    "message": f"Switched to context {context_name}",
                    "details": result
                }
            except Exception as e:
                return {
                    "status": "error",
                    "error": f"Failed to switch context: {str(e)}"
                }
