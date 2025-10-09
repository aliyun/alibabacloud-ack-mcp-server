import pytest

import ack_inspect_handler as module_under_test


class FakeServer:
    def __init__(self):
        self.tools = {}

    def tool(self, name: str = None, description: str = None):
        def decorator(func):
            key = name or getattr(func, "__name__", "unnamed")
            self.tools[key] = func
            return func
        return decorator


class FakeRequestContext:
    def __init__(self, lifespan_context=None):
        self.lifespan_context = lifespan_context or {}


class FakeContext:
    def __init__(self, lifespan_context=None):
        self.request_context = FakeRequestContext(lifespan_context)


class FakeReport:
    def __init__(self, report_id):
        self.report_id = report_id


class FakeListResponseBody:
    def __init__(self, reports):
        self.reports = reports


class FakeListResponse:
    def __init__(self, reports):
        self.body = FakeListResponseBody(reports)


class FakeSummary:
    def __init__(self, error_count=0, warn_count=0, normal_count=0, advice_count=0, unknown_count=0):
        self.error_count = error_count
        self.warn_count = warn_count
        self.normal_count = normal_count
        self.advice_count = advice_count
        self.unknown_count = unknown_count


class FakeCheckItem:
    def __init__(self, category="stability", name="test", target_type="Node", targets=None, description="test desc", fix="test fix", check_item_uid="test-uid", level="warning"):
        self.category = category
        self.name = name
        self.target_type = target_type
        self.targets = targets or ["test-target"]
        self.description = description
        self.fix = fix
        self.check_item_uid = check_item_uid
        self.level = level


class FakeCreateResponseBody:
    def __init__(self, reports=None):
        self.reports = reports or [FakeReport("report-123")]
        self.report_id = self.reports[0].report_id if self.reports else "report-123"


class FakeCreateResponse:
    def __init__(self, reports=None):
        self.body = FakeCreateResponseBody(reports)


class FakeDetailResponseBody:
    def __init__(self, status="completed", end_time="2025-09-16T08:09:44Z", summary=None, check_items=None):
        self.status = status
        self.endTime = end_time
        self.summary = summary or FakeSummary()
        self.check_item_results = check_items or []


class FakeDetailResponse:
    def __init__(self, status="completed", end_time="2025-09-16T08:09:44Z", summary=None, check_items=None):
        self.body = FakeDetailResponseBody(status, end_time, summary, check_items)


class FakeCSClient:
    def __init__(self, list_response=None, detail_response=None, create_response=None):
        self._list_response = list_response
        self._detail_response = detail_response
        self._create_response = create_response

    async def run_cluster_inspect_with_options_async(self, cluster_id, request, headers, runtime):
        return self._create_response

    async def list_cluster_inspect_reports_with_options_async(self, cluster_id, request, headers, runtime):
        return self._list_response

    async def get_cluster_inspect_report_detail_with_options_async(self, cluster_id, report_id, request, headers, runtime):
        return self._detail_response


def make_handler_and_tool():
    server = FakeServer()
    module_under_test.InspectHandler(server, {"test_mode": True})  # 启用测试模式
    return server.tools["query_inspect_report"]


@pytest.mark.asyncio
async def test_query_inspect_report_success():
    tool = make_handler_and_tool()

    # Mock successful responses
    create_response = FakeCreateResponse([FakeReport("report-123")])
    list_response = FakeListResponse([FakeReport("report-123")])
    check_item = FakeCheckItem(
        category="stability",
        name="Linux kernel has a risk of high CPU utilization",
        target_type="Node",
        targets=["cn-beijing.1.31.81", "cn-beijing.10.131.3"],
        description="Some versions of Alibaba Cloud Linux 3 and other operating systems utilize a Linux kernel with a flaw that causes CPU utilization spikes during high-frequency invocations of LRU Maps.",
        fix="Please refer to [Document](https://www.alibabacloud.com/help/en/ack/product-overview/product-announcement-announcement-on-the-problem-of-intermittent-high-cpu-usage-on-linux-nodes-with-terway) to upgrade kernel.",
        check_item_uid="check-001",
        level="warning"
    )
    summary = FakeSummary(error_count=3, warn_count=3, normal_count=3, advice_count=3, unknown_count=3)
    detail_response = FakeDetailResponse(
        status="completed",
        end_time="2025-09-16T08:09:44Z",
        summary=summary,
        check_items=[check_item]
    )

    def cs_client_factory(_region: str, config=None):
        return FakeCSClient(list_response, detail_response, create_response)

    ctx = FakeContext({
        "config": {"region_id": "cn-hangzhou"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, cluster_id="caxxxxxxxxxxx", region_id="cn-hangzhou", is_result_exception=True)

    assert result.report_status == "completed"
    assert result.report_finish_time == "2025-09-16T08:09:44Z"
    assert result.summary.errorCount == 3
    assert result.summary.warnCount == 3
    assert result.summary.normalCount == 3
    assert len(result.checkItemResults) == 1
    assert result.checkItemResults[0].name == "Linux kernel has a risk of high CPU utilization"
    assert result.checkItemResults[0].category == "stability"
    assert result.checkItemResults[0].targetType == "Node"  # 使用target_type后映射到targetType
    assert result.checkItemResults[0].level == "warning"
    assert len(result.checkItemResults[0].targets) == 2
    assert result.error is None


@pytest.mark.asyncio
async def test_query_inspect_report_no_reports():
    tool = make_handler_and_tool()

    # Mock successful create but empty list response
    create_response = FakeCreateResponse([FakeReport("report-123")])
    list_response = FakeListResponse([])
    def cs_client_factory(_region: str, config=None):
        return FakeCSClient(list_response, None, create_response)

    ctx = FakeContext({
        "config": {"region_id": "cn-hangzhou"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, cluster_id="caxxxxxxxxxxx", region_id="cn-hangzhou", is_result_exception=True)

    assert "error" in result
    assert result["error"]["error_code"] == "NO_INSPECT_REPORT"


@pytest.mark.asyncio
async def test_query_inspect_report_no_report_id():
    tool = make_handler_and_tool()

    # Mock report without report_id
    class FakeReportNoId:
        pass  # No report_id attribute

    create_response = FakeCreateResponse([FakeReport("report-123")])
    list_response = FakeListResponse([FakeReportNoId()])
    def cs_client_factory(_region: str, config=None):
        return FakeCSClient(list_response, None, create_response)

    ctx = FakeContext({
        "config": {"region_id": "cn-hangzhou"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, cluster_id="caxxxxxxxxxxx", region_id="cn-hangzhou", is_result_exception=True)

    assert "error" in result
    assert result["error"]["error_code"] == "NO_REPORT_ID"


def test_handler_registers_tool():
    server = FakeServer()
    module_under_test.InspectHandler(server, {})
    assert "query_inspect_report" in server.tools
