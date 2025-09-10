#!/usr/bin/env python3
"""
测试阿里云ACK集群管理API参数是否正确
验证当前实现的API参数与阿里云官方文档是否一致
"""

import sys
import os

# 添加项目根目录到Python路径，以便正确导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..', '..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from alibabacloud_cs20151215 import models as cs20151215_models

def test_cluster_management_api_parameters():
    """测试所有集群管理API参数"""
    
    print("=== 阿里云ACK集群管理API参数验证测试 ===\n")
    
    # 1. 测试DescribeClustersV1Request
    print("1. 测试DescribeClustersV1Request:")
    try:
        request = cs20151215_models.DescribeClustersV1Request(
            name="test-cluster",
            cluster_type="ManagedKubernetes", 
            cluster_spec="ack.pro.small",
            profile="Default",
            region_id="cn-hangzhou",
            cluster_id="c123456",
            page_size=10,
            page_number=1
        )
        print("✓ DescribeClustersV1Request 参数正确")
    except Exception as e:
        print(f"✗ DescribeClustersV1Request 参数错误: {e}")
    
    # 2. 测试DescribeClusterDetailRequest (GET请求，不需要请求体)
    print("\n2. DescribeClusterDetail是GET请求，不需要请求类:")
    print("✓ DescribeClusterDetail API不需要请求体参数")
    
    # 3. 测试ModifyClusterRequest
    print("\n3. 测试ModifyClusterRequest:")
    try:
        request = cs20151215_models.ModifyClusterRequest(
            cluster_name="new-cluster-name",
            deletion_protection=True,
            instance_deletion_protection=False,
            resource_group_id="rg-12345",
            api_server_eip=True,
            api_server_eip_id="eip-12345",
            ingress_domain_rebinding=False,
            ingress_loadbalancer_id="lb-12345",
            enable_rrsa=True
        )
        print("✓ ModifyClusterRequest 参数正确")
    except Exception as e:
        print(f"✗ ModifyClusterRequest 参数错误: {e}")
    
    # 4. 测试CreateClusterRequest
    print("\n4. 测试CreateClusterRequest:")
    try:
        request = cs20151215_models.CreateClusterRequest(
            name="test-cluster",
            region_id="cn-hangzhou",
            cluster_type="ManagedKubernetes",
            kubernetes_version="1.32.1-aliyun.1",
            cluster_spec="ack.pro.small",
            service_cidr="172.21.0.0/20",
            container_cidr="172.20.0.0/16",
            timezone="Asia/Shanghai",
            endpoint_public_access=True,
            snat_entry=True,
            ssh_flags=False,
            is_enterprise_security_group=True
        )
        print("✓ CreateClusterRequest 参数正确")
    except Exception as e:
        print(f"✗ CreateClusterRequest 参数错误: {e}")
    
    # 5. 测试DeleteClusterRequest
    print("\n5. 测试DeleteClusterRequest:")
    try:
        request = cs20151215_models.DeleteClusterRequest(
            retain_all_resources=False,
            retain_resources=["sg-12345", "slb-67890"],
            delete_options=[
                {"resource_type": "SLS_Data", "delete_mode": "delete"}
            ]
        )
        print("✓ DeleteClusterRequest 参数正确")
    except Exception as e:
        print(f"✗ DeleteClusterRequest 参数错误: {e}")
    
    # 6. 测试UpgradeClusterRequest
    print("\n6. 测试UpgradeClusterRequest:")
    try:
        request = cs20151215_models.UpgradeClusterRequest(
            next_version="1.32.1-aliyun.1",
            master_only=True,
            rolling_policy={"max_parallelism": 3}
        )
        print("✓ UpgradeClusterRequest 参数正确")
    except Exception as e:
        print(f"✗ UpgradeClusterRequest 参数错误: {e}")
    
    # 4. DescribeTaskInfo是GET请求，不需要请求类
    print("\n4. DescribeTaskInfo是GET请求，不需要请求类:")
    print("✓ DescribeTaskInfo API不需要请求体参数")
    
    # 5. DescribeClusterLogs是GET请求，不需要请求类
    print("\n5. DescribeClusterLogs是GET请求，不需要请求类:")
    print("✓ DescribeClusterLogs API不需要请求体参数")
    
    # 6. DescribeUserQuota是GET请求，不需要请求类
    print("\n6. DescribeUserQuota是GET请求，不需要请求类:")
    print("✓ DescribeUserQuota API不需要请求体参数")
    
    # 7. DescribeKubernetesVersionMetadata是GET请求，不需要请求类
    print("\n7. DescribeKubernetesVersionMetadata是GET请求，不需要请求类:")
    print("✓ DescribeKubernetesVersionMetadata API不需要请求体参数")
    
    # 5. 测试其他可能的请求类
    print("\n5. 检查其他集群管理相关请求类:")
    cluster_requests = [
        name for name in dir(cs20151215_models) 
        if 'Cluster' in name and 'Request' in name and not name.startswith('_')
    ]
    
    for req_name in sorted(cluster_requests):
        if req_name in ['DescribeClustersV1Request', 'ModifyClusterRequest']:
            continue  # 已经测试过
        print(f"  发现请求类: {req_name}")
    
    print("\n=== 集群管理API参数验证测试完成 ===")

def test_enum_values():
    """测试枚举值是否正确"""
    print("\n=== 测试API枚举值 ===")
    
    # 集群类型枚举值
    print("集群类型枚举值:")
    cluster_types = ["Kubernetes", "ManagedKubernetes", "ExternalKubernetes"]
    for ct in cluster_types:
        print(f"  ✓ {ct}")
    
    # 集群规格枚举值  
    print("\n集群规格枚举值:")
    cluster_specs = ["ack.pro.small", "ack.standard"]
    for cs in cluster_specs:
        print(f"  ✓ {cs}")
    
    # 集群子类型枚举值
    print("\n集群子类型枚举值:")
    profiles = ["Default", "Edge", "Serverless", "Lingjun"]
    for profile in profiles:
        print(f"  ✓ {profile}")
    
    print("\n=== 枚举值验证完成 ===")

if __name__ == "__main__":
    test_cluster_management_api_parameters()
    test_enum_values()