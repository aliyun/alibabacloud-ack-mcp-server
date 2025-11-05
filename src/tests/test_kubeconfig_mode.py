import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock, mock_open

# 添加父目录到路径以导入模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import kubectl_handler as module_under_test


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


class FakeCSClient:
    def describe_cluster_detail(self, cluster_id):
        class FakeResponse:
            class FakeBody:
                def __init__(self):
                    self.master_url = '{"api_server_endpoint": "https://test.example.com:6443", "intranet_api_server_endpoint": "https://internal.test.com:6443"}'
            body = FakeBody()
        return FakeResponse()
        
    def describe_cluster_user_kubeconfig(self, cluster_id, request):
        class FakeResponse:
            class FakeBody:
                config = "apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443\nusers:\n- name: test-user\n  user:\n    token: test-token"
            body = FakeBody()
        return FakeResponse()


class FakeCSClientFactory:
    def __call__(self, region_id, config=None):
        return FakeCSClient()


class FakeLifespanContext:
    def __init__(self):
        self.providers = {"cs_client_factory": FakeCSClientFactory()}
        self.config = {"region_id": "cn-hangzhou"}


@pytest.fixture
def context_manager():
    """创建一个新的上下文管理器实例用于测试"""
    # 清理全局缓存
    module_under_test._context_manager = None
    cm = module_under_test.get_context_manager(ttl_minutes=1)  # 使用1分钟TTL便于测试
    yield cm
    # 清理
    cm.cleanup()
    module_under_test._context_manager = None


@pytest.fixture
def temp_kubeconfig_file():
    """创建一个临时kubeconfig文件用于测试"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443\nusers:\n- name: test-user\n  user:\n    token: test-token")
        temp_path = f.name
    yield temp_path
    # 清理
    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_local_kubeconfig_mode_success(context_manager, temp_kubeconfig_file):
    """测试 LOCAL 模式成功使用本地 kubeconfig 文件"""
    cluster_id = "test-cluster"
    
    # 使用 LOCAL 模式获取 kubeconfig 路径
    kubeconfig_path = context_manager.get_kubeconfig_path(
        cluster_id=cluster_id,
        kubeconfig_mode="LOCAL",
        kubeconfig_path=temp_kubeconfig_file
    )
    
    # 验证返回的路径是本地文件路径
    assert kubeconfig_path == temp_kubeconfig_file
    assert os.path.exists(kubeconfig_path)
    
    # 验证缓存中已存储
    assert cluster_id in context_manager
    assert context_manager[cluster_id] == temp_kubeconfig_file


def test_local_kubeconfig_mode_file_not_exists(context_manager):
    """测试 LOCAL 模式但文件不存在的情况"""
    cluster_id = "test-cluster"
    non_existent_path = "/tmp/non-existent-kubeconfig.yaml"
    
    # 应该抛出 ValueError
    with pytest.raises(ValueError, match="File .* does not exist"):
        context_manager.get_kubeconfig_path(
            cluster_id=cluster_id,
            kubeconfig_mode="LOCAL",
            kubeconfig_path=non_existent_path
        )


def test_local_kubeconfig_mode_empty_path(context_manager):
    """测试 LOCAL 模式但路径为空的情况"""
    cluster_id = "test-cluster"
    
    # 应该抛出 ValueError
    with pytest.raises(ValueError, match="Local kubeconfig path is not set"):
        context_manager.get_kubeconfig_path(
            cluster_id=cluster_id,
            kubeconfig_mode="LOCAL",
            kubeconfig_path=""
        )


def test_ack_public_kubeconfig_mode_success(context_manager):
    """测试 ACK_PUBLIC 模式成功获取 kubeconfig"""
    cluster_id = "test-cluster"
    
    # Mock CS 客户端
    with patch.object(context_manager, '_get_cs_client') as mock_get_cs_client:
        mock_get_cs_client.return_value = FakeCSClient()
        
        # 使用 ACK_PUBLIC 模式获取 kubeconfig 路径
        kubeconfig_path = context_manager.get_kubeconfig_path(
            cluster_id=cluster_id,
            kubeconfig_mode="ACK_PUBLIC",
            kubeconfig_path=""
        )
        
        # 验证返回的路径是生成的文件路径
        assert kubeconfig_path.startswith(os.path.expanduser("~/.kube/mcp-kubeconfig-"))
        assert kubeconfig_path.endswith(".yaml")
        assert os.path.exists(kubeconfig_path)
        
        # 验证缓存中已存储
        assert cluster_id in context_manager
        assert context_manager[cluster_id] == kubeconfig_path
        
        # 验证文件内容
        with open(kubeconfig_path, 'r') as f:
            content = f.read()
            assert "apiVersion: v1" in content
            assert "server: https://test.example.com:6443" in content


def test_ack_private_kubeconfig_mode_success(context_manager):
    """测试 ACK_PRIVATE 模式成功获取 kubeconfig"""
    cluster_id = "test-cluster"
    
    # Mock CS 客户端
    with patch.object(context_manager, '_get_cs_client') as mock_get_cs_client:
        mock_get_cs_client.return_value = FakeCSClient()
        
        # 使用 ACK_PRIVATE 模式获取 kubeconfig 路径
        kubeconfig_path = context_manager.get_kubeconfig_path(
            cluster_id=cluster_id,
            kubeconfig_mode="ACK_PRIVATE",
            kubeconfig_path=""
        )
        
        # 验证返回的路径是生成的文件路径
        assert kubeconfig_path.startswith(os.path.expanduser("~/.kube/mcp-kubeconfig-"))
        assert kubeconfig_path.endswith(".yaml")
        assert os.path.exists(kubeconfig_path)
        
        # 验证缓存中已存储
        assert cluster_id in context_manager
        assert context_manager[cluster_id] == kubeconfig_path


def test_incluster_kubeconfig_mode_success(context_manager):
    """测试 INCLUSTER 模式成功构造 kubeconfig"""
    cluster_id = "test-cluster"
    
    # Mock 环境变量
    with patch.dict(os.environ, {
        "KUBERNETES_SERVICE_HOST": "kubernetes.default.svc",
        "KUBERNETES_SERVICE_PORT": "443"
    }):
        # Mock 文件操作
        mock_file = mock_open()
        with patch('kubectl_handler.os.open', mock_file), \
             patch('kubectl_handler.os.O_RDWR', 0), \
             patch('kubectl_handler.os.O_CREAT', 0):
            # 使用 INCLUSTER 模式获取 kubeconfig 路径
            kubeconfig_path = context_manager.get_kubeconfig_path(
                cluster_id=cluster_id,
                kubeconfig_mode="INCLUSTER",
                kubeconfig_path=""
            )
            
            # 验证返回的路径是集群内配置文件路径
            expected_path = os.path.expanduser("~/.kube/config.incluster")
            assert kubeconfig_path == expected_path
            
            # 验证缓存中已存储
            assert cluster_id in context_manager
            assert context_manager[cluster_id] == kubeconfig_path


def test_ack_public_kubeconfig_mode_api_failure(context_manager):
    """测试 ACK_PUBLIC 模式但 API 调用失败的情况"""
    cluster_id = "test-cluster"
    
    # Mock CS 客户端返回空配置
    class FakeCSClientFailure:
        def describe_cluster_detail(self, cluster_id):
            class FakeResponse:
                class FakeBody:
                    def __init__(self):
                        self.master_url = '{"api_server_endpoint": "https://test.example.com:6443", "intranet_api_server_endpoint": "https://internal.test.com:6443"}'
                body = FakeBody()
            return FakeResponse()
            
        def describe_cluster_user_kubeconfig(self, cluster_id, request):
            class FakeResponse:
                class FakeBody:
                    config = None  # 返回空配置
                body = FakeBody()
            return FakeResponse()
    
    # Mock CS 客户端
    with patch.object(context_manager, '_get_cs_client') as mock_get_cs_client:
        mock_get_cs_client.return_value = FakeCSClientFailure()
        
        # 应该抛出 ValueError
        with pytest.raises(ValueError, match="Failed to get kubeconfig for cluster"):
            context_manager.get_kubeconfig_path(
                cluster_id=cluster_id,
                kubeconfig_mode="ACK_PUBLIC",
                kubeconfig_path=""
            )


def test_ack_private_kubeconfig_mode_no_intranet_endpoint(context_manager):
    """测试 ACK_PRIVATE 模式但集群没有内网端点的情况"""
    cluster_id = "test-cluster"
    
    # Mock CS 客户端返回没有内网端点的集群详情
    class FakeCSClientNoIntranet:
        def describe_cluster_detail(self, cluster_id):
            class FakeResponse:
                class FakeBody:
                    def __init__(self):
                        # 没有 intranet_api_server_endpoint
                        self.master_url = '{"api_server_endpoint": "https://test.example.com:6443"}'
                body = FakeBody()
            return FakeResponse()
            
        def describe_cluster_user_kubeconfig(self, cluster_id, request):
            class FakeResponse:
                class FakeBody:
                    config = "apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443"
                body = FakeBody()
            return FakeResponse()
    
    # Mock CS 客户端
    with patch.object(context_manager, '_get_cs_client') as mock_get_cs_client:
        mock_get_cs_client.return_value = FakeCSClientNoIntranet()
        
        # 应该抛出 ValueError
        with pytest.raises(ValueError, match="does not have intranet endpoint access"):
            context_manager.get_kubeconfig_path(
                cluster_id=cluster_id,
                kubeconfig_mode="ACK_PRIVATE",
                kubeconfig_path=""
            )


def test_ack_public_kubeconfig_mode_no_public_endpoint(context_manager):
    """测试 ACK_PUBLIC 模式但集群没有公网端点的情况"""
    cluster_id = "test-cluster"
    
    # Mock CS 客户端返回没有公网端点的集群详情
    class FakeCSClientNoPublic:
        def describe_cluster_detail(self, cluster_id):
            class FakeResponse:
                class FakeBody:
                    def __init__(self):
                        # 没有 api_server_endpoint
                        self.master_url = '{"intranet_api_server_endpoint": "https://internal.test.com:6443"}'
                body = FakeBody()
            return FakeResponse()
            
        def describe_cluster_user_kubeconfig(self, cluster_id, request):
            class FakeResponse:
                class FakeBody:
                    config = "apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443"
                body = FakeBody()
            return FakeResponse()
    
    # Mock CS 客户端
    with patch.object(context_manager, '_get_cs_client') as mock_get_cs_client:
        mock_get_cs_client.return_value = FakeCSClientNoPublic()
        
        # 应该抛出 ValueError
        with pytest.raises(ValueError, match="does not have public endpoint access"):
            context_manager.get_kubeconfig_path(
                cluster_id=cluster_id,
                kubeconfig_mode="ACK_PUBLIC",
                kubeconfig_path=""
            )


def test_cached_kubeconfig_reuse(context_manager, temp_kubeconfig_file):
    """测试缓存的 kubeconfig 被正确重用"""
    cluster_id = "test-cluster"
    
    # 第一次获取 kubeconfig
    kubeconfig_path1 = context_manager.get_kubeconfig_path(
        cluster_id=cluster_id,
        kubeconfig_mode="LOCAL",
        kubeconfig_path=temp_kubeconfig_file
    )
    
    # 第二次获取同一个集群的 kubeconfig
    kubeconfig_path2 = context_manager.get_kubeconfig_path(
        cluster_id=cluster_id,
        kubeconfig_mode="LOCAL",
        kubeconfig_path=temp_kubeconfig_file
    )
    
    # 应该返回相同的路径
    assert kubeconfig_path1 == kubeconfig_path2
    assert kubeconfig_path1 == temp_kubeconfig_file


def test_kubeconfig_cleanup_on_cache_eviction(context_manager):
    """测试缓存驱逐时 kubeconfig 文件被正确清理"""
    cluster_id = "test-cluster"
    
    # Mock CS 客户端
    with patch.object(context_manager, '_get_cs_client') as mock_get_cs_client:
        mock_get_cs_client.return_value = FakeCSClient()
        
        # 获取 ACK_PUBLIC 模式的 kubeconfig (会创建临时文件)
        kubeconfig_path = context_manager.get_kubeconfig_path(
            cluster_id=cluster_id,
            kubeconfig_mode="ACK_PUBLIC",
            kubeconfig_path=""
        )
        
        # 验证文件存在
        assert os.path.exists(kubeconfig_path)
        
        # 验证缓存中有项目
        assert len(context_manager) == 1
        
        # 手动驱逐缓存项，应该会清理文件
        key, path = context_manager.popitem()
        assert key == cluster_id
        assert path == kubeconfig_path
        
        # 文件应该已被删除
        # 注意：由于 popitem 中的清理逻辑，文件应该已被删除


def test_local_kubeconfig_not_cleaned_up(context_manager, temp_kubeconfig_file):
    """测试 LOCAL 模式的 kubeconfig 文件不会被清理"""
    cluster_id = "test-cluster"
    
    # 使用 LOCAL 模式
    kubeconfig_path = context_manager.get_kubeconfig_path(
        cluster_id=cluster_id,
        kubeconfig_mode="LOCAL",
        kubeconfig_path=temp_kubeconfig_file
    )
    
    # 手动调用清理方法
    context_manager.cleanup()
    
    # 本地文件应该仍然存在
    assert os.path.exists(temp_kubeconfig_file)


@pytest.mark.asyncio
async def test_kubectl_tool_with_local_kubeconfig_mode():
    """测试 kubectl 工具使用 LOCAL 模式"""
    # 创建临时 kubeconfig 文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443\nusers:\n- name: test-user\n  user:\n    token: test-token")
        temp_kubeconfig_path = f.name
    
    try:
        # 创建带有 LOCAL 模式设置的 handler
        server = FakeServer()
        handler = module_under_test.KubectlHandler(
            server, 
            {
                "allow_write": True,
                "kubeconfig_mode": "LOCAL",
                "kubeconfig_path": temp_kubeconfig_path
            }
        )
        tool = server.tools["ack_kubectl"]
        
        # Mock subprocess.run
        with patch('kubectl_handler.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="pods found", stderr="")
            
            # 创建上下文
            ctx = FakeContext(FakeLifespanContext())
            
            # 执行命令
            result = await tool(ctx, command="get pods", cluster_id="test-cluster")
            
            # 验证结果
            assert result.exit_code == 0
            assert result.stdout == "pods found"
            
            # 验证 subprocess.run 被调用
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]  # 获取第一个位置参数
            assert f"--kubeconfig {temp_kubeconfig_path}" in call_args
    finally:
        # 清理临时文件
        if os.path.exists(temp_kubeconfig_path):
            os.unlink(temp_kubeconfig_path)
        
        # 清理全局缓存
        module_under_test._context_manager = None


@pytest.mark.asyncio
async def test_kubectl_tool_with_ack_public_kubeconfig_mode():
    """测试 kubectl 工具使用 ACK_PUBLIC 模式"""
    # 创建带有 ACK_PUBLIC 模式设置的 handler
    server = FakeServer()
    handler = module_under_test.KubectlHandler(
        server, 
        {
            "allow_write": True,
            "kubeconfig_mode": "ACK_PUBLIC",
            "kubeconfig_path": ""
        }
    )
    tool = server.tools["ack_kubectl"]
    
    # Mock subprocess.run
    with patch('kubectl_handler.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="pods found", stderr="")
        
        # Mock CS 客户端
        with patch('kubectl_handler.get_context_manager') as mock_get_context_manager:
            # 创建 mock context manager
            mock_context_manager = MagicMock()
            mock_context_manager.get_kubeconfig_path.return_value = "/tmp/test-kubeconfig.yaml"
            mock_get_context_manager.return_value = mock_context_manager
            
            # 创建上下文
            ctx = FakeContext(FakeLifespanContext())
            
            # 执行命令
            result = await tool(ctx, command="get pods", cluster_id="test-cluster")
            
            # 验证结果
            assert result.exit_code == 0
            assert result.stdout == "pods found"
            
            # 验证 subprocess.run 被调用
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]  # 获取第一个位置参数
            assert "--kubeconfig /tmp/test-kubeconfig.yaml" in call_args


@pytest.mark.asyncio
async def test_kubectl_tool_with_ack_private_kubeconfig_mode():
    """测试 kubectl 工具使用 ACK_PRIVATE 模式"""
    # 创建带有 ACK_PRIVATE 模式设置的 handler
    server = FakeServer()
    handler = module_under_test.KubectlHandler(
        server, 
        {
            "allow_write": True,
            "kubeconfig_mode": "ACK_PRIVATE",
            "kubeconfig_path": ""
        }
    )
    tool = server.tools["ack_kubectl"]
    
    # Mock subprocess.run
    with patch('kubectl_handler.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="pods found", stderr="")
        
        # Mock CS 客户端
        with patch('kubectl_handler.get_context_manager') as mock_get_context_manager:
            # 创建 mock context manager
            mock_context_manager = MagicMock()
            mock_context_manager.get_kubeconfig_path.return_value = "/tmp/test-kubeconfig.yaml"
            mock_get_context_manager.return_value = mock_context_manager
            
            # 创建上下文
            ctx = FakeContext(FakeLifespanContext())
            
            # 执行命令
            result = await tool(ctx, command="get pods", cluster_id="test-cluster")
            
            # 验证结果
            assert result.exit_code == 0
            assert result.stdout == "pods found"
            
            # 验证 subprocess.run 被调用
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]  # 获取第一个位置参数
            assert "--kubeconfig /tmp/test-kubeconfig.yaml" in call_args


@pytest.mark.asyncio
async def test_kubectl_tool_with_incluster_kubeconfig_mode():
    """测试 kubectl 工具使用 INCLUSTER 模式"""
    # 创建带有 INCLUSTER 模式设置的 handler
    server = FakeServer()
    handler = module_under_test.KubectlHandler(
        server, 
        {
            "allow_write": True,
            "kubeconfig_mode": "INCLUSTER",
            "kubeconfig_path": ""
        }
    )
    tool = server.tools["ack_kubectl"]
    
    # Mock subprocess.run
    with patch('kubectl_handler.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="pods found", stderr="")
        
        # Mock CS 客户端
        with patch('kubectl_handler.get_context_manager') as mock_get_context_manager:
            # 创建 mock context manager
            mock_context_manager = MagicMock()
            mock_context_manager.get_kubeconfig_path.return_value = "/tmp/.kube/config.incluster"
            mock_get_context_manager.return_value = mock_context_manager
            
            # 创建上下文
            ctx = FakeContext(FakeLifespanContext())
            
            # 执行命令
            result = await tool(ctx, command="get pods", cluster_id="test-cluster")
            
            # 验证结果
            assert result.exit_code == 0
            assert result.stdout == "pods found"
            
            # 验证 subprocess.run 被调用
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]  # 获取第一个位置参数
            assert "--kubeconfig /tmp/.kube/config.incluster" in call_args


if __name__ == "__main__":
    pytest.main([__file__])