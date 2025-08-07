package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/tools/clientcmd"
)

func main() {
	// 创建一个新的 MCP 服务器
	s := server.NewMCPServer(
		"Kubectl Get MCP Server",
		"1.0.0",
		server.WithResourceCapabilities(true, true),
		server.WithToolCapabilities(true),
		server.WithPromptCapabilities(true),
		server.WithLogging(),
	)

	// 增加一个 kubectl get 工具
	get_tool := mcp.NewTool(
		"kubectl_get",
		mcp.WithDescription("Get Kubernetes resources using kubectl get functionality"),
		mcp.WithString("resource",
			mcp.Required(),
			mcp.Description("Resource type to get (e.g., pods, services, deployments, nodes, configmaps, secrets)"),
		),
		mcp.WithString("namespace",
			mcp.DefaultString("default"),
			mcp.Description("Namespace to query (default: default)"),
		),
		mcp.WithString("name",
			mcp.Description("Specific resource name to get"),
		),
	)

	// 增加工具处理程序
	s.AddTool(get_tool, kubectlGetHandler)

	// 启动 MCP Server 服务
	log.Println("Starting StreamableHTTP server on :8080")
	httpServer := server.NewStreamableHTTPServer(s)

	// 启动 HTTP server
	go func() {
		if err := httpServer.Start(":8080"); err != nil {
			log.Fatal(err)
		}
	}()

	// 优雅退出
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down server...")

	// 关闭 HTTP server
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := httpServer.Shutdown(ctx); err != nil {
		log.Printf("HTTP server Shutdown: %v", err)
	} else {
		log.Println("Server gracefully stopped")
	}
}

func kubectlGetHandler(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	// 解析请求参数
	resource, err := request.RequireString("resource")
	if err != nil {
		return mcp.NewToolResultError("resource parameter is required"), nil
	}
	namespace := request.GetString("namespace", "default")
	name := request.GetString("name", "")

	// 创建 Kubernetes 客户端
	clientset, err := getKubernetesClient()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Failed to create Kubernetes client: %v", err)), nil
	}

	// 获取资源
	result, err := getResource(clientset, resource, namespace, name)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Failed to get resource: %v", err)), nil
	}
	// 返回结果
	return mcp.NewToolResultText(result), nil
}

func getKubernetesClient() (*kubernetes.Clientset, error) {
	// Get kubeconfig path
	kubeconfig := filepath.Join(os.Getenv("HOME"), ".kube", "config")

	// Build config from kubeconfig
	config, err := clientcmd.BuildConfigFromFlags("", kubeconfig)
	if err != nil {
		return nil, fmt.Errorf("failed to build kubeconfig: %v", err)
	}

	// Create clientset
	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create clientset: %v", err)
	}

	return clientset, nil
}

func getResource(clientset *kubernetes.Clientset, resource, namespace, name string) (string, error) {
	switch resource {
	case "pods":
		return getPods(clientset, namespace, name)
	case "services":
		return getServices(clientset, namespace, name)
	case "deployments":
		return getDeployments(clientset, namespace, name)
	case "nodes":
		return getNodes(clientset, name)
	case "configmaps":
		return getConfigMaps(clientset, namespace, name)
	case "secrets":
		return getSecrets(clientset, namespace, name)
	default:
		return "", fmt.Errorf("unsupported resource type: %s", resource)
	}
}

func getPods(clientset *kubernetes.Clientset, namespace, name string) (string, error) {
	if namespace == "all" {
		namespace = metav1.NamespaceAll
	}
	if name != "" {
		pod, err := clientset.CoreV1().Pods(namespace).Get(context.TODO(), name, metav1.GetOptions{})
		if err != nil {
			return "", err
		}
		return formatOutput(pod)
	}

	pods, err := clientset.CoreV1().Pods(namespace).List(context.TODO(), metav1.ListOptions{})
	if err != nil {
		return "", err
	}
	return formatOutput(pods)
}

func getServices(clientset *kubernetes.Clientset, namespace, name string) (string, error) {
	if namespace == "all" {
		namespace = metav1.NamespaceAll
	}
	if name != "" {
		service, err := clientset.CoreV1().Services(namespace).Get(context.TODO(), name, metav1.GetOptions{})
		if err != nil {
			return "", err
		}
		return formatOutput(service)
	}

	services, err := clientset.CoreV1().Services(namespace).List(context.TODO(), metav1.ListOptions{})
	if err != nil {
		return "", err
	}
	return formatOutput(services)
}

func getDeployments(clientset *kubernetes.Clientset, namespace, name string) (string, error) {
	if namespace == "all" {
		namespace = metav1.NamespaceAll
	}
	if name != "" {
		deployment, err := clientset.AppsV1().Deployments(namespace).Get(context.TODO(), name, metav1.GetOptions{})
		if err != nil {
			return "", err
		}
		return formatOutput(deployment)
	}

	deployments, err := clientset.AppsV1().Deployments(namespace).List(context.TODO(), metav1.ListOptions{})
	if err != nil {
		return "", err
	}
	return formatOutput(deployments)
}

func getNodes(clientset *kubernetes.Clientset, name string) (string, error) {
	if name != "" {
		node, err := clientset.CoreV1().Nodes().Get(context.TODO(), name, metav1.GetOptions{})
		if err != nil {
			return "", err
		}
		return formatOutput(node)
	}

	nodes, err := clientset.CoreV1().Nodes().List(context.TODO(), metav1.ListOptions{})
	if err != nil {
		return "", err
	}
	return formatOutput(nodes)
}

func getConfigMaps(clientset *kubernetes.Clientset, namespace, name string) (string, error) {
	if namespace == "all" {
		namespace = metav1.NamespaceAll
	}
	if name != "" {
		configMap, err := clientset.CoreV1().ConfigMaps(namespace).Get(context.TODO(), name, metav1.GetOptions{})
		if err != nil {
			return "", err
		}
		return formatOutput(configMap)
	}

	configMaps, err := clientset.CoreV1().ConfigMaps(namespace).List(context.TODO(), metav1.ListOptions{})
	if err != nil {
		return "", err
	}
	return formatOutput(configMaps)
}

func getSecrets(clientset *kubernetes.Clientset, namespace, name string) (string, error) {
	if namespace == "all" {
		namespace = metav1.NamespaceAll
	}
	if name != "" {
		secret, err := clientset.CoreV1().Secrets(namespace).Get(context.TODO(), name, metav1.GetOptions{})
		if err != nil {
			return "", err
		}
		return formatOutput(secret)
	}

	secrets, err := clientset.CoreV1().Secrets(namespace).List(context.TODO(), metav1.ListOptions{})
	if err != nil {
		return "", err
	}
	return formatOutput(secrets)
}

func formatOutput(obj interface{}) (string, error) {
	jsonData, err := json.MarshalIndent(obj, "", "  ")
	if err != nil {
		return "", err
	}
	return string(jsonData), nil
}
