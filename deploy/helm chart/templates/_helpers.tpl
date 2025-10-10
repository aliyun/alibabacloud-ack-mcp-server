{{/*
Expand the name of the chart.
*/}}
{{- define "ack-mcp-server.name" -}}
{{- default "ack-mcp-server" (and .Values .Values.nameOverride) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "ack-mcp-server.fullname" -}}
{{- $name := default "ack-mcp-server" (and .Values .Values.nameOverride) }}
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
{{- define "ack-mcp-server.chart" -}}
{{- printf "%s-%s" "ack-mcp-server" "0.1.0" | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ack-mcp-server.labels" -}}
helm.sh/chart: {{ include "ack-mcp-server.chart" . }}
{{ include "ack-mcp-server.selectorLabels" . }}
app.kubernetes.io/version: "1.16.0"
app.kubernetes.io/managed-by: {{ default "Helm" (and .Release .Release.Service) }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ack-mcp-server.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ack-mcp-server.name" . }}
app.kubernetes.io/instance: {{ default "mcp" (and .Release .Release.Name) }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "ack-mcp-server.serviceAccountName" -}}
{{- if and .Values .Values.serviceAccount .Values.serviceAccount.create }}
{{- default (include "ack-mcp-server.fullname" .) (and .Values .Values.serviceAccount .Values.serviceAccount.name) }}
{{- else }}
{{- default "default" (and .Values .Values.serviceAccount .Values.serviceAccount.name) }}
{{- end }}
{{- end }}