#!/usr/bin/env python3
"""
测试阿里云ACK诊断和巡检API参数是否正确
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

def test_api_parameters():
    """测试所有API参数"""
    
    print("=== 阿里云ACK API参数验证测试 ===\n")
    
    # 1. 测试CreateClusterDiagnosisRequest
    print("1. 测试CreateClusterDiagnosisRequest:")
    try:
        request = cs20151215_models.CreateClusterDiagnosisRequest(
            type="cluster",  # 官方文档: node, ingress, cluster, memory, pod, service, network
            target={"name": "test-node"}
        )
        print("✓ CreateClusterDiagnosisRequest 参数正确")
    except Exception as e:
        print(f"✗ CreateClusterDiagnosisRequest 参数错误: {e}")
    
    # 2. 测试GetClusterDiagnosisResultRequest  
    print("\n2. 测试GetClusterDiagnosisResultRequest:")
    try:
        request = cs20151215_models.GetClusterDiagnosisResultRequest()
        print("✓ GetClusterDiagnosisResultRequest 参数正确")
    except Exception as e:
        print(f"✗ GetClusterDiagnosisResultRequest 参数错误: {e}")
    
    # 3. 测试GetClusterDiagnosisCheckItemsRequest
    print("\n3. 测试GetClusterDiagnosisCheckItemsRequest:")
    try:
        request = cs20151215_models.GetClusterDiagnosisCheckItemsRequest(
            language="zh_CN"
        )
        print("✓ GetClusterDiagnosisCheckItemsRequest 参数正确")
    except Exception as e:
        print(f"✗ GetClusterDiagnosisCheckItemsRequest 参数错误: {e}")
    
    # 4. 测试RunClusterInspectRequest
    print("\n4. 测试RunClusterInspectRequest:")
    try:
        request = cs20151215_models.RunClusterInspectRequest(
            client_token="test-token"
        )
        print("✓ RunClusterInspectRequest 参数正确")
    except Exception as e:
        print(f"✗ RunClusterInspectRequest 参数错误: {e}")
    
    # 5. 测试CreateClusterInspectConfigRequest
    print("\n5. 测试CreateClusterInspectConfigRequest:")
    try:
        request = cs20151215_models.CreateClusterInspectConfigRequest(
            enabled=True,
            recurrence="FREQ=DAILY;BYHOUR=10;BYMINUTE=15",
            disabled_check_items=["NginxIngressServiceAnnotationMultiTargets"]
        )
        print("✓ CreateClusterInspectConfigRequest 参数正确")
    except Exception as e:
        print(f"✗ CreateClusterInspectConfigRequest 参数错误: {e}")
    
    # 6. 测试UpdateClusterInspectConfigRequest
    print("\n6. 测试UpdateClusterInspectConfigRequest:")
    try:
        request = cs20151215_models.UpdateClusterInspectConfigRequest(
            enabled=True,
            schedule_time="FREQ=DAILY;BYHOUR=10;BYMINUTE=15",
            disabled_check_items=["NginxIngressServiceAnnotationMultiTargets"]
        )
        print("✓ UpdateClusterInspectConfigRequest 参数正确")
    except Exception as e:
        print(f"✗ UpdateClusterInspectConfigRequest 参数错误: {e}")
    
    # 7. GetClusterInspectConfig是GET请求，不需要请求类
    print("\n7. GetClusterInspectConfig是GET请求，不需要请求类:")
    print("✓ GetClusterInspectConfig API不需要请求体参数")
    
    # 8. 测试ListClusterInspectReportsRequest (如果存在)
    print("\n8. 测试ListClusterInspectReportsRequest:")
    try:
        request = cs20151215_models.ListClusterInspectReportsRequest(
            next_token="test-token",
            max_results=20
        )
        print("✓ ListClusterInspectReportsRequest 参数正确")
    except Exception as e:
        print(f"✗ ListClusterInspectReportsRequest 参数错误: {e}")
    
    # 9. 测试GetClusterInspectReportDetailRequest (如果存在)
    print("\n9. 测试GetClusterInspectReportDetailRequest:")
    try:
        request = cs20151215_models.GetClusterInspectReportDetailRequest(
            language="zh_CN",
            category="security",
            target_type="node",
            level="warning",
            enable_filter=True,
            next_token="test-token",
            max_results=20
        )
        print("✓ GetClusterInspectReportDetailRequest 参数正确")
    except Exception as e:
        print(f"✗ GetClusterInspectReportDetailRequest 参数错误: {e}")
    
    print("\n=== API参数验证测试完成 ===")

if __name__ == "__main__":
    test_api_parameters()