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
Check if autoscaling is enabled for a component spec.
Usage: {{ include "ai-stack.autoscalingEnabled" .Values.openwebui }}
Returns "true" or "".
*/}}
{{- define "ai-stack.autoscalingEnabled" -}}
{{- if and (hasKey . "autoscaling") .autoscaling.enabled -}}true{{- end -}}
{{- end }}

{{/*
Resolve component enabled state for components with non-standard value paths.
Usage: {{ include "ai-stack.componentEnabled" (dict "Values" .Values "component" "otel-collector") }}
*/}}
{{- define "ai-stack.componentEnabled" -}}
{{- $component := .component -}}
{{- if eq $component "otel-collector" -}}
  {{- .Values.global.otel.enabled -}}
{{- else if eq $component "ingestion-worker" -}}
  {{- .Values.ingestionWorker.enabled -}}
{{- else if eq $component "open-terminal" -}}
  {{- .Values.openTerminal.enabled -}}
{{- else if eq $component "postgres" -}}
  {{- and .Values.postgres.enabled (eq .Values.postgres.mode "standalone") -}}
{{- else -}}
  {{- (index .Values $component).enabled -}}
{{- end -}}
{{- end }}

{{/*
Network policy egress rule for a component.
Usage: {{ include "ai-stack.netpolEgress" (dict "enabled" .Values.ollama.enabled "name" "ollama" "port" 11434) }}
*/}}
{{- define "ai-stack.netpolEgress" -}}
{{- if .enabled }}
- to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: {{ .name }}
  ports:
    - protocol: TCP
      port: {{ .port }}
{{- end }}
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
=============================================================================
PostgreSQL connection abstraction helpers.
These resolve hostname, port, secret references, and connection URI
regardless of whether mode is standalone, cnpg, or external.
=============================================================================
*/}}

{{/*
PostgreSQL internal service/host name.
  standalone: <release>-postgres  (Service created by deployment.yaml)
  cnpg:       <release>-postgres-rw  (CNPG convention: <cluster>-rw)
              or <release>-postgres-pooler-rw when pooler is enabled
  external:   user-supplied host
*/}}
{{- define "ai-stack.postgresHost" -}}
{{- if eq .Values.postgres.mode "external" -}}
  {{- required "postgres.external.host is required when mode=external" .Values.postgres.external.host -}}
{{- else if eq .Values.postgres.mode "cnpg" -}}
  {{- if .Values.postgres.cnpg.pooler.enabled -}}
    {{- printf "%s-postgres-pooler-%s" .Release.Name .Values.postgres.cnpg.pooler.type -}}
  {{- else -}}
    {{- printf "%s-postgres-rw" .Release.Name -}}
  {{- end -}}
{{- else -}}
  {{- include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "postgres") -}}
{{- end -}}
{{- end }}

{{/*
PostgreSQL port.
*/}}
{{- define "ai-stack.postgresPort" -}}
{{- if eq .Values.postgres.mode "external" -}}
  {{- .Values.postgres.external.port | default 5432 -}}
{{- else -}}
  {{- .Values.postgres.service.port | default 5432 -}}
{{- end -}}
{{- end }}

{{/*
PostgreSQL secret name containing the password.
  standalone: <release>-postgres-secret   (managed by secrets.yaml)
  cnpg:       <release>-postgres-app      (CNPG convention: <cluster>-app)
  external:   user-supplied secret name
*/}}
{{- define "ai-stack.postgresSecretName" -}}
{{- if eq .Values.postgres.mode "external" -}}
  {{- required "postgres.external.existingSecret.name is required when mode=external" .Values.postgres.external.existingSecret.name -}}
{{- else if eq .Values.postgres.mode "cnpg" -}}
  {{- printf "%s-postgres-app" .Release.Name -}}
{{- else -}}
  {{- printf "%s-secret" (include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "postgres")) -}}
{{- end -}}
{{- end }}

{{/*
PostgreSQL secret key for the password field.
  standalone: password
  cnpg:       password  (CNPG app secret uses "password")
  external:   user-supplied key
*/}}
{{- define "ai-stack.postgresSecretKey" -}}
{{- if eq .Values.postgres.mode "external" -}}
  {{- .Values.postgres.external.existingSecret.key | default "password" -}}
{{- else -}}
  password
{{- end -}}
{{- end }}

{{/*
PostgreSQL SSL mode for connection URIs.
*/}}
{{- define "ai-stack.postgresSslMode" -}}
{{- .Values.postgres.tls.mode | default "disable" -}}
{{- end }}

{{/*
PostgreSQL connection URI template.
Consumers inject _PG_PASSWORD env var from the secret, then reference this
URI which uses the variable substitution: $(_PG_PASSWORD).
Usage in env:
  - name: POSTGRES_URI
    value: {{ include "ai-stack.postgresURI" . }}
*/}}
{{- define "ai-stack.postgresURI" -}}
{{- $host := include "ai-stack.postgresHost" . -}}
{{- $port := include "ai-stack.postgresPort" . -}}
{{- $ssl := include "ai-stack.postgresSslMode" . -}}
{{- printf "postgresql://%s:$(_PG_PASSWORD)@%s:%s/%s?sslmode=%s" .Values.postgres.user $host $port .Values.postgres.database $ssl -}}
{{- end }}

{{/*
=============================================================================
External API helpers.
Build the OPENAI_API_BASE_URLS and OPENAI_API_KEYS strings for Open WebUI
by combining internal service endpoints with external API providers.
=============================================================================
*/}}

{{/*
Construct OPENAI_API_BASE_URLS: internal endpoints + external provider URLs.
Internal endpoints (Pipelines, Ollama) come first, followed by each
externalAPIs.providers[].baseUrl.
*/}}
{{- define "ai-stack.openaiBaseUrls" -}}
{{- $urls := list -}}
{{- if .Values.pipelines.enabled -}}
  {{- $urls = append $urls (printf "http://%s:%v" (include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "pipelines")) (.Values.pipelines.service.port | toString)) -}}
{{- end -}}
{{- if .Values.ollama.enabled -}}
  {{- $urls = append $urls (printf "http://%s:%v" (include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "ollama")) (.Values.ollama.service.port | toString)) -}}
{{- end -}}
{{- if and .Values.externalAPIs.enabled .Values.externalAPIs.providers -}}
  {{- range .Values.externalAPIs.providers -}}
    {{- $urls = append $urls .baseUrl -}}
  {{- end -}}
{{- end -}}
{{- join ";" $urls -}}
{{- end }}

{{/*
Construct OPENAI_API_KEYS: placeholder keys for internal endpoints + secret
references for external providers.
Internal endpoints use "0" (Open WebUI convention for no-auth endpoints).
External provider keys use Kubernetes variable substitution: $(_EXTAPI_KEY_<index>)
which are injected as env vars from Secrets.
*/}}
{{- define "ai-stack.openaiApiKeys" -}}
{{- $keys := list -}}
{{- if .Values.pipelines.enabled -}}
  {{- $keys = append $keys "0" -}}
{{- end -}}
{{- if .Values.ollama.enabled -}}
  {{- $keys = append $keys "0" -}}
{{- end -}}
{{- if and .Values.externalAPIs.enabled .Values.externalAPIs.providers -}}
  {{- range $i, $p := .Values.externalAPIs.providers -}}
    {{- $keys = append $keys (printf "$(_EXTAPI_KEY_%d)" $i) -}}
  {{- end -}}
{{- end -}}
{{- join ";" $keys -}}
{{- end }}

{{/*
External API secret name for a provider.
Usage: {{ include "ai-stack.extapiSecretName" (dict "Release" .Release "Chart" .Chart "provider" $provider) }}
*/}}
{{- define "ai-stack.extapiSecretName" -}}
{{- printf "%s-extapi-%s-secret" .Release.Name .provider.name | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{/*
Standard restricted container security context for non-root containers.
Usage: {{ include "ai-stack.restrictedSecurityContext" . | nindent N }}
Override readOnlyRootFilesystem or runAsUser by passing a dict:
  {{ include "ai-stack.restrictedSecurityContext" (dict "readOnlyRootFilesystem" true "runAsUser" 999) }}
*/}}
{{- define "ai-stack.restrictedSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: {{ .readOnlyRootFilesystem | default false }}
runAsNonRoot: true
runAsUser: {{ .runAsUser | default 1000 }}
capabilities:
  drop:
    - ALL
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Node scheduling: nodeSelector + tolerations from global values.
Usage: {{ include "ai-stack.nodeScheduling" . | nindent N }}
*/}}
{{- define "ai-stack.nodeScheduling" -}}
{{- with .Values.global.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.global.tolerations }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Qdrant API key environment variable from secret.
Usage: {{ include "ai-stack.qdrantApiKeyEnv" . | nindent N }}
*/}}
{{- define "ai-stack.qdrantApiKeyEnv" -}}
{{- if .Values.qdrant.enabled }}
- name: QDRANT_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "qdrant") }}-secret
      key: api-key
{{- end }}
{{- end }}

{{/*
Authelia OIDC environment variables for Open WebUI.
Injects OAUTH_* env vars when authelia.enabled=true.
Usage: {{ include "ai-stack.autheliaOauthEnv" . | nindent N }}
*/}}
{{- define "ai-stack.autheliaOauthEnv" -}}
{{- if .Values.authelia.enabled }}
- name: OAUTH_PROVIDER_NAME
  value: "Authelia"
- name: OAUTH_CLIENT_ID
  value: {{ .Values.authelia.oidc.clientId | quote }}
- name: OAUTH_CLIENT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "authelia") }}-secret
      key: oidc-client-secret
- name: OPENID_PROVIDER_URL
  value: {{ .Values.authelia.oidc.issuerUrl | quote }}
- name: OAUTH_SCOPES
  value: {{ join " " .Values.authelia.oidc.scopes | quote }}
- name: ENABLE_OAUTH_SIGNUP
  value: "true"
{{- end }}
{{- end }}

{{/*
Ingress resource template (shared by openwebui, workbench, langgraph, etc.).
Usage: {{ include "ai-stack.ingress" (dict "root" . "component" "openwebui" "ingress" .Values.openwebui.ingress) }}
*/}}
{{- define "ai-stack.ingress" -}}
{{- if .ingress.enabled }}
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "ai-stack.componentName" (dict "Release" .root.Release "Chart" .root.Chart "component" .component) }}
  labels:
    {{- include "ai-stack.labels" .root | nindent 4 }}
  {{- with .ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- if .ingress.className }}
  ingressClassName: {{ .ingress.className }}
  {{- end }}
  {{- if .ingress.tls }}
  tls:
    {{- range .ingress.tls }}
    - hosts:
        {{- range .hosts }}
        - {{ . | quote }}
        {{- end }}
      secretName: {{ .secretName }}
    {{- end }}
  {{- end }}
  rules:
    {{- range .ingress.hosts }}
    - host: {{ .host | quote }}
      http:
        paths:
          {{- range .paths }}
          - path: {{ .path }}
            pathType: {{ .pathType }}
            backend:
              service:
                name: {{ include "ai-stack.componentName" (dict "Release" $.root.Release "Chart" $.root.Chart "component" $.component) }}
                port:
                  name: http
          {{- end }}
    {{- end }}
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
