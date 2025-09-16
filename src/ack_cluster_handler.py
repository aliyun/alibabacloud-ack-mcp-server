


class ACKClusterHandler:
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

    def _register_tools(self):
        """Register addon management related tools."""

        @self.server.tool(
            name="describe_clusters_brief",
            description="Quick list brief all clusters and output. default page_size 500."
        )
        async def describe_clusters_brief(
                ctx: Context,
                resource_type: str = Field(
                    ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
                ),
                regions: Optional[List[str]] = Field(None, description="Region list to query; defaults to common regions"),
                page_size: Optional[int] = Field(500, description="Page size, default 500"),
        ) -> Dict[str, Any]:
            """List clusters with brief fields across regions.

            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                regions: Region list to query; defaults to common regions
                page_size: Page size, default 500

            Returns:
                Brief cluster list with fields: name, cluster_id, state, region_id, node_count, cluster_type
            """
            # Get base config for AK
            try:
                lifespan_config = ctx.request_context.lifespan_context.get("config", {})
            except Exception as e:
                logger.error(f"Failed to get lifespan config: {e}")
                return {"error": "Failed to access lifespan context"}

            target_regions = regions or DEFAULT_REGIONS
            brief_list: List[Dict[str, Any]] = []
            errors: List[Dict[str, Any]] = []

            for region in target_regions:
                try:
                    cs_client = _build_cs_client_for_region(lifespan_config, region)
                    request = cs20151215_models.DescribeClustersV1Request(
                        page_size=min(page_size or 500, 500),
                        page_number=1,
                        region_id=region,
                    )
                    runtime = util_models.RuntimeOptions()
                    headers = {}
                    response = await cs_client.describe_clusters_v1with_options_async(request, headers, runtime)
                    clusters = _serialize_sdk_object(response.body.clusters) if response.body and response.body.clusters else []
                    for c in clusters:
                        # 兼容 SDK 字段命名
                        brief_list.append({
                            "name": c.get("name") or c.get("cluster_name"),
                            "cluster_id": c.get("cluster_id") or c.get("clusterId"),
                            "state": c.get("state") or c.get("cluster_state") or c.get("status"),
                            "region_id": c.get("region_id") or region,
                            "node_count": c.get("node_count") or c.get("current_node_count") or c.get("size"),
                            "cluster_type": c.get("cluster_type") or c.get("clusterType"),
                        })
                except Exception as e:
                    logger.warning(f"describe_clusters_brief failed for region {region}: {e}")
                    errors.append({"region": region, "error": str(e)})
                    continue

            return {
                "clusters": brief_list,
                "count": len(brief_list),
                "regions": target_regions,
                "errors": errors or None,
            }