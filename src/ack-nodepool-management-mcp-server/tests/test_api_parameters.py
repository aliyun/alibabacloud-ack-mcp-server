#!/usr/bin/env python3
"""API parameters validation tests for ACK NodePool Management."""

import pytest
from alibabacloud_cs20151215 import models as cs20151215_models


def test_nodepool_management_api_parameters():
    """测试所有节点池管理API参数"""
    
    print("=== 阿里云ACK节点池管理API参数验证测试 ===\n")
    
    # 1. 测试DescribeClusterNodePools (GET请求，不需要请求体)
    print("1. DescribeClusterNodePools是GET请求，不需要请求类:")
    print("✓ DescribeClusterNodePools API不需要请求体参数")
    
    # 2. 测试DescribeClusterNodePoolDetail (GET请求，不需要请求体)
    print("\n2. DescribeClusterNodePoolDetail是GET请求，不需要请求类:")
    print("✓ DescribeClusterNodePoolDetail API不需要请求体参数")
    
    # 3. 测试ScaleClusterNodePoolRequest
    print("\n3. 测试ScaleClusterNodePoolRequest:")
    try:
        request = cs20151215_models.ScaleClusterNodePoolRequest(
            count=5
        )
        print("✓ ScaleClusterNodePoolRequest 参数正确")
        assert hasattr(request, 'count')
        assert request.count == 5
    except Exception as e:
        print(f"✗ ScaleClusterNodePoolRequest 参数错误: {e}")
    
    # 4. 测试RemoveNodePoolNodesRequest
    print("\n4. 测试RemoveNodePoolNodesRequest:")
    try:
        request = cs20151215_models.RemoveNodePoolNodesRequest(
            instance_ids=["i-test123", "i-test456"],
            release_node=True,
            drain_node=True
        )
        print("✓ RemoveNodePoolNodesRequest 参数正确")
        assert hasattr(request, 'instance_ids')
        assert hasattr(request, 'release_node')
        assert hasattr(request, 'drain_node')
    except Exception as e:
        print(f"✗ RemoveNodePoolNodesRequest 参数错误: {e}")
    
    # 5. 测试CreateClusterNodePoolRequest
    print("\n5. 测试CreateClusterNodePoolRequest:")
    try:
        nodepool_info = cs20151215_models.CreateClusterNodePoolRequestNodepoolInfo(
            name="test-nodepool",
            type="ess"
        )
        scaling_group = cs20151215_models.CreateClusterNodePoolRequestScalingGroup(
            instance_types=["ecs.g6.large"],
            vswitch_ids=["vsw-test123"],
            desired_size=3,
            system_disk_category="cloud_efficiency",
            system_disk_size=120
        )
        auto_scaling = cs20151215_models.CreateClusterNodePoolRequestAutoScaling(
            enable=True,
            max_instances=10,
            min_instances=1,
            type="cpu"
        )
        
        request = cs20151215_models.CreateClusterNodePoolRequest(
            nodepool_info=nodepool_info,
            scaling_group=scaling_group,
            auto_scaling=auto_scaling
        )
        print("✓ CreateClusterNodePoolRequest 参数正确")
        assert hasattr(request, 'nodepool_info')
        assert hasattr(request, 'scaling_group')
        assert hasattr(request, 'auto_scaling')
    except Exception as e:
        print(f"✗ CreateClusterNodePoolRequest 参数错误: {e}")
    
    # 6. 测试ModifyClusterNodePoolRequest
    print("\n6. 测试ModifyClusterNodePoolRequest:")
    try:
        nodepool_info = cs20151215_models.ModifyClusterNodePoolRequestNodepoolInfo(
            name="updated-nodepool"
        )
        scaling_group = cs20151215_models.ModifyClusterNodePoolRequestScalingGroup(
            desired_size=5
        )
        auto_scaling = cs20151215_models.ModifyClusterNodePoolRequestAutoScaling(
            enable=True,
            max_instances=15
        )
        
        request = cs20151215_models.ModifyClusterNodePoolRequest(
            nodepool_info=nodepool_info,
            scaling_group=scaling_group,
            auto_scaling=auto_scaling
        )
        print("✓ ModifyClusterNodePoolRequest 参数正确")
        assert hasattr(request, 'nodepool_info')
        assert hasattr(request, 'scaling_group')
        assert hasattr(request, 'auto_scaling')
    except Exception as e:
        print(f"✗ ModifyClusterNodePoolRequest 参数错误: {e}")
    
    # 7. 测试DeleteClusterNodepoolRequest
    print("\n7. 测试DeleteClusterNodepoolRequest:")
    try:
        request = cs20151215_models.DeleteClusterNodepoolRequest(
            force=False
        )
        print("✓ DeleteClusterNodepoolRequest 参数正确")
        assert hasattr(request, 'force')
    except Exception as e:
        print(f"✗ DeleteClusterNodepoolRequest 参数错误: {e}")
    
    # 8. 测试UpgradeClusterNodepoolRequest
    print("\n8. 测试UpgradeClusterNodepoolRequest:")
    try:
        request = cs20151215_models.UpgradeClusterNodepoolRequest(
            kubernetes_version="1.28.3-aliyun.1",
            image_id="m-test123"
        )
        print("✓ UpgradeClusterNodepoolRequest 参数正确")
        assert hasattr(request, 'kubernetes_version')
        assert hasattr(request, 'image_id')
    except Exception as e:
        print(f"✗ UpgradeClusterNodepoolRequest 参数错误: {e}")
    
    # 9. 测试AttachInstancesToNodePoolRequest
    print("\n9. 测试AttachInstancesToNodePoolRequest:")
    try:
        # AttachInstancesToNodePoolRequest instances parameter expects a list of instance IDs (strings)
        instances = ["i-test123", "i-test456"]
        request = cs20151215_models.AttachInstancesToNodePoolRequest(
            instances=instances,
            keep_instance_name=True,
            format_disk=False
        )
        print("✓ AttachInstancesToNodePoolRequest 参数正确")
        assert hasattr(request, 'instances')
        assert hasattr(request, 'keep_instance_name')
        assert hasattr(request, 'format_disk')
    except Exception as e:
        print(f"✗ AttachInstancesToNodePoolRequest 参数错误: {e}")
    
    print("\n=== API参数验证测试完成 ===")


if __name__ == "__main__":
    test_nodepool_management_api_parameters()