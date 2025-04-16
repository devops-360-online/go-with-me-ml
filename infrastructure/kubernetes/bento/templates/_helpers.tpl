{{/*
Expand the name of the chart.
*/}}
{{- define "bento-stack.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "bento-stack.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "bento-stack.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "bento-stack.labels" -}}
helm.sh/chart: {{ include "bento-stack.chart" . }}
{{ include "bento-stack.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "bento-stack.selectorLabels" -}}
app.kubernetes.io/name: {{ include "bento-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create a generic ConfigMap with flexibility for data from a file or inline values
Usage: include "bento.configmap" (dict "root" $ "name" "component-name" "dataFromFile" "path/to/file.yml" "dataInline" (dict "key" "value"))
*/}}
{{- define "bento.configmap" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $dataFromFile := .dataFromFile -}}
{{- $dataInline := .dataInline -}}
apiVersion: v1
kind: ConfigMap
metadata:
  name: bento-config-{{ $name }}
  namespace: {{ $root.Release.Namespace }}
  labels:
    {{- include "bento-stack.labels" $root | nindent 4 }}
    app.kubernetes.io/component: {{ $name }}
data:
  {{- if $dataFromFile }}
  config.yaml: |-
    {{- $root.Files.Get $dataFromFile | nindent 4 }}
  {{- end }}
  {{- if $dataInline }}
  {{- range $key, $value := $dataInline }}
  {{ $key }}: |-
    {{- tpl ($value | toYaml) $root | nindent 4 }}
  {{- end }}
  {{- end }}
{{- end -}} 