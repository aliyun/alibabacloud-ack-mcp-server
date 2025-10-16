import json
import os
import sys
import tempfile
from unittest.mock import patch

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import runtime_provider as module_under_test


class TestPrometheusGuidance:
    """测试 Prometheus 指标指引功能"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.provider = module_under_test.ACKClusterRuntimeProvider()

    def test_initialize_prometheus_guidance_success(self):
        """测试成功初始化 Prometheus 指标指引"""
        with patch.object(self.provider, '_load_metrics_dictionary') as mock_load_metrics, \
             patch.object(self.provider, '_load_promql_best_practice') as mock_load_practice:
            
            mock_load_metrics.return_value = {"test_metrics": {"metrics": []}}
            mock_load_practice.return_value = {"test_practice": {"rules": []}}
            
            result = self.provider.initialize_prometheus_guidance()
            
            assert result["initialized"] is True
            assert result["error"] is None
            assert "metrics_dictionary" in result
            assert "promql_best_practice" in result
            assert result["metrics_dictionary"] == {"test_metrics": {"metrics": []}}
            assert result["promql_best_practice"] == {"test_practice": {"rules": []}}

    def test_initialize_prometheus_guidance_directory_not_found(self):
        """测试目录不存在时的处理"""
        with patch('os.path.isdir', return_value=False):
            result = self.provider.initialize_prometheus_guidance()
            
            assert result["initialized"] is True
            assert result["error"] is None
            assert result["metrics_dictionary"] == {}
            assert result["promql_best_practice"] == {}

    def test_load_metrics_dictionary_success(self):
        """测试成功加载指标定义文件"""
        test_data = {
            "metrics": [
                {
                    "name": "test_metric",
                    "category": "cpu",
                    "labels": ["pod", "container"],
                    "description": "Test metric",
                    "type": "gauge"
                }
            ]
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_metrics.json")
            with open(test_file, 'w', encoding='utf-8') as f:
                json.dump(test_data, f)
            
            result = self.provider._load_metrics_dictionary(temp_dir)
            
            assert "test_metrics" in result
            assert result["test_metrics"] == test_data

    def test_load_metrics_dictionary_invalid_json(self):
        """测试加载无效JSON文件时的处理"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "invalid.json")
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write("invalid json content")
            
            result = self.provider._load_metrics_dictionary(temp_dir)
            
            # 应该跳过无效文件，返回空字典
            assert result == {}

    def test_load_promql_best_practice_success(self):
        """测试成功加载PromQL最佳实践文件"""
        test_data = {
            "rules": [
                {
                    "rule_name": "test_rule",
                    "category": "cpu",
                    "labels": ["pod"],
                    "description": "Test rule",
                    "expression": "test_expression",
                    "severity": "Critical"
                }
            ]
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_practice.json")
            with open(test_file, 'w', encoding='utf-8') as f:
                json.dump(test_data, f)
            
            result = self.provider._load_promql_best_practice(temp_dir)
            
            assert "test_practice" in result
            assert result["test_practice"] == test_data

    def test_query_metrics_by_category_and_label_success(self):
        """测试成功查询指标定义"""
        test_guidance = {
            "initialized": True,
            "metrics_dictionary": {
                "test_file": {
                    "metrics": [
                        {
                            "name": "cpu_usage",
                            "category": "cpu",
                            "labels": ["pod", "container"],
                            "description": "CPU usage metric",
                            "type": "gauge"
                        },
                        {
                            "name": "memory_usage",
                            "category": "memory",
                            "labels": ["pod", "container"],
                            "description": "Memory usage metric",
                            "type": "gauge"
                        }
                    ]
                }
            }
        }
        
        with patch.object(self.provider, 'initialize_prometheus_guidance', return_value=test_guidance):
            result = self.provider.query_metrics_by_category_and_label("cpu", "pod")
            
            assert len(result) == 1
            assert result[0]["file_source"] == "test_file"
            assert result[0]["metric"]["name"] == "cpu_usage"
            assert result[0]["metric"]["category"] == "cpu"

    def test_query_metrics_by_category_and_label_no_match(self):
        """测试没有匹配指标时的查询"""
        test_guidance = {
            "initialized": True,
            "metrics_dictionary": {
                "test_file": {
                    "metrics": [
                        {
                            "name": "cpu_usage",
                            "category": "cpu",
                            "labels": ["node"],  # 不包含 "pod"
                            "description": "CPU usage metric",
                            "type": "gauge"
                        }
                    ]
                }
            }
        }
        
        with patch.object(self.provider, 'initialize_prometheus_guidance', return_value=test_guidance):
            result = self.provider.query_metrics_by_category_and_label("cpu", "pod")
            
            assert len(result) == 0

    def test_query_metrics_by_category_and_label_not_initialized(self):
        """测试未初始化时的查询"""
        test_guidance = {
            "initialized": False,
            "error": "Test error"
        }
        
        with patch.object(self.provider, 'initialize_prometheus_guidance', return_value=test_guidance):
            result = self.provider.query_metrics_by_category_and_label("cpu", "pod")
            
            assert len(result) == 0

    def test_query_promql_practices_by_category_and_label_success(self):
        """测试成功查询PromQL最佳实践"""
        test_guidance = {
            "initialized": True,
            "promql_best_practice": {
                "test_file": {
                    "rules": [
                        {
                            "rule_name": "cpu_high_usage",
                            "category": "cpu",
                            "labels": ["pod"],
                            "description": "CPU usage is high",
                            "expression": "cpu_usage > 80",
                            "severity": "Critical"
                        },
                        {
                            "rule_name": "memory_high_usage",
                            "category": "memory",
                            "labels": ["pod"],
                            "description": "Memory usage is high",
                            "expression": "memory_usage > 80",
                            "severity": "Warning"
                        }
                    ]
                }
            }
        }
        
        with patch.object(self.provider, 'initialize_prometheus_guidance', return_value=test_guidance):
            result = self.provider.query_promql_practices_by_category_and_label("cpu", "pod")
            
            assert len(result) == 1
            assert result[0]["file_source"] == "test_file"
            assert result[0]["rule"]["rule_name"] == "cpu_high_usage"
            assert result[0]["rule"]["category"] == "cpu"

    def test_query_promql_practices_by_category_and_label_no_match(self):
        """测试没有匹配规则时的查询"""
        test_guidance = {
            "initialized": True,
            "promql_best_practice": {
                "test_file": {
                    "rules": [
                        {
                            "rule_name": "cpu_high_usage",
                            "category": "cpu",
                            "labels": ["node"],  # 不包含 "pod"
                            "description": "CPU usage is high",
                            "expression": "cpu_usage > 80",
                            "severity": "Critical"
                        }
                    ]
                }
            }
        }
        
        with patch.object(self.provider, 'initialize_prometheus_guidance', return_value=test_guidance):
            result = self.provider.query_promql_practices_by_category_and_label("cpu", "pod")
            
            assert len(result) == 0

    def test_query_promql_practices_by_category_and_label_not_initialized(self):
        """测试未初始化时的查询"""
        test_guidance = {
            "initialized": False,
            "error": "Test error"
        }
        
        with patch.object(self.provider, 'initialize_prometheus_guidance', return_value=test_guidance):
            result = self.provider.query_promql_practices_by_category_and_label("cpu", "pod")
            
            assert len(result) == 0

    def test_case_insensitive_category_matching(self):
        """测试分类匹配的大小写不敏感"""
        test_guidance = {
            "initialized": True,
            "metrics_dictionary": {
                "test_file": {
                    "metrics": [
                        {
                            "name": "cpu_usage",
                            "category": "CPU",  # 大写
                            "labels": ["pod"],
                            "description": "CPU usage metric",
                            "type": "gauge"
                        }
                    ]
                }
            }
        }
        
        with patch.object(self.provider, 'initialize_prometheus_guidance', return_value=test_guidance):
            result = self.provider.query_metrics_by_category_and_label("cpu", "pod")  # 小写查询
            
            assert len(result) == 1
            assert result[0]["metric"]["name"] == "cpu_usage"

    def test_different_file_structures(self):
        """测试不同文件结构的处理"""
        test_guidance = {
            "initialized": True,
            "metrics_dictionary": {
                "file1": {
                    "metrics": [
                        {
                            "name": "metric1",
                            "category": "cpu",
                            "labels": ["pod"],
                            "description": "Metric 1",
                            "type": "gauge"
                        }
                    ]
                },
                "file2": [  # 直接是数组结构
                    {
                        "name": "metric2",
                        "category": "memory",
                        "labels": ["pod"],
                        "description": "Metric 2",
                        "type": "gauge"
                    }
                ]
            }
        }
        
        with patch.object(self.provider, 'initialize_prometheus_guidance', return_value=test_guidance):
            cpu_result = self.provider.query_metrics_by_category_and_label("cpu", "pod")
            memory_result = self.provider.query_metrics_by_category_and_label("memory", "pod")
            
            assert len(cpu_result) == 1
            assert cpu_result[0]["metric"]["name"] == "metric1"
            
            assert len(memory_result) == 1
            assert memory_result[0]["metric"]["name"] == "metric2"
