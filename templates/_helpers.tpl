{{/*
Expand the name of the chart.
*/}}
{{- define "ai-stack.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ai-stack.fullname" -}}
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
Chart label helper.
*/}}
{{- define "ai-stack.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to all resources.
*/}}
{{- define "ai-stack.labels" -}}
helm.sh/chart: {{ include "ai-stack.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/part-of: ai-stack
{{- end }}

{{/*
Selector labels for a specific component.
Usage: {{ include "ai-stack.selectorLabels" (dict "Release" .Release "component" "openwebui") }}
*/}}
{{- define "ai-stack.selectorLabels" -}}
app.kubernetes.io/name: {{ .component }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Component fullname helper.
Usage: {{ include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "openwebui") }}
*/}}
{{- define "ai-stack.componentName" -}}
{{- printf "%s-%s" .Release.Name .component | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
OTel environment variables (injected into all pods when otel.enabled=true).
*/}}
{{- define "ai-stack.otelEnv" -}}
{{- if .Values.global.otel.enabled }}
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: {{ .Values.global.otel.endpoint | quote }}
- name: OTEL_EXPORTER_OTLP_PROTOCOL
  value: {{ .Values.global.otel.protocol | quote }}
- name: OTEL_EXPORTER_OTLP_INSECURE
  value: {{ .Values.global.otel.insecure | quote }}
- name: OTEL_SERVICE_NAME
  value: {{ .component | quote }}
- name: OTEL_RESOURCE_ATTRIBUTES
  value: "deployment.environment={{ .Values.global.profile }},service.namespace={{ .Release.Namespace }},service.version={{ .Chart.AppVersion }}"
{{- end }}
{{- end }}

{{/*
DNS config helper — applies global.dnsConfig when set.
*/}}
{{- define "ai-stack.dnsConfig" -}}
{{- with .Values.global.dnsConfig }}
dnsConfig:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Image pull secrets helper.
*/}}
{{- define "ai-stack.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- range . }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Pod annotations (global + component + auto-injected version).
Automatically adds assurance.platform/version from Chart.AppVersion.
*/}}
{{- define "ai-stack.podAnnotations" -}}
{{- $merged := dict "assurance.platform/version" .Chart.AppVersion }}
{{- with .Values.global.podAnnotations }}
{{- $merged = merge $merged . }}
{{- end }}
{{- with .componentAnnotations }}
{{- $merged = merge $merged . }}
{{- end }}
{{- toYaml $merged }}
{{- end }}

{{/*
Topology spread constraints for prod multi-replica deployments.
*/}}
{{- define "ai-stack.topologySpread" -}}
{{- $multiReplica := or (gt (int .replicaCount) 1) (.autoscaling | default false) -}}
{{- if and (eq .Values.global.profile "prod") $multiReplica }}
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        {{- include "ai-stack.selectorLabels" (dict "Release" .Release "component" .component) | nindent 8 }}
{{- end }}
{{- end }}

{{/*
Init container: wait for a TCP service to become reachable.
Uses busybox nc; no external dependencies.
*/}}
{{- define "ai-stack.waitFor" -}}
- name: wait-for-{{ .name }}
  image: busybox:1.37
  command: ['sh', '-c', 'until nc -z {{ .host }} {{ .port }} ; do echo "waiting for {{ .name }}..."; sleep 2; done']
  securityContext:
    allowPrivilegeEscalation: false
    readOnlyRootFilesystem: true
    runAsNonRoot: true
    runAsUser: 65534
    capabilities:
      drop:
        - ALL
    seccompProfile:
      type: RuntimeDefault
  resources:
    requests:
      cpu: 10m
      memory: 16Mi
    limits:
      cpu: 50m
      memory: 32Mi
{{- end }}
