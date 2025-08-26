{{/*
Expand the name of the chart.
*/}}
{{- define "mcp-chart.name" -}}
{{- default "mcp-chart" (and .Values .Values.nameOverride) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "mcp-chart.fullname" -}}
{{- $name := default "mcp-chart" (and .Values .Values.nameOverride) }}
{{- $releaseName := default "mcp" (and .Release .Release.Name) }}
{{- if contains $name $releaseName }}
{{- $releaseName | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" $releaseName $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "mcp-chart.chart" -}}
{{- printf "%s-%s" "mcp-chart" "0.1.0" | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "mcp-chart.labels" -}}
helm.sh/chart: {{ include "mcp-chart.chart" . }}
{{ include "mcp-chart.selectorLabels" . }}
app.kubernetes.io/version: "1.16.0"
app.kubernetes.io/managed-by: {{ default "Helm" (and .Release .Release.Service) }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "mcp-chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mcp-chart.name" . }}
app.kubernetes.io/instance: {{ default "mcp" (and .Release .Release.Name) }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "mcp-chart.serviceAccountName" -}}
{{- if and .Values .Values.serviceAccount .Values.serviceAccount.create }}
{{- default (include "mcp-chart.fullname" .) (and .Values .Values.serviceAccount .Values.serviceAccount.name) }}
{{- else }}
{{- default "default" (and .Values .Values.serviceAccount .Values.serviceAccount.name) }}
{{- end }}
{{- end }}