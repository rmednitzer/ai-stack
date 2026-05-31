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
Returns "true" or "".
Usage: {{ if include "ai-stack.componentEnabled" (dict "Values" .Values "component" "otel-collector") }}
*/}}
{{- define "ai-stack.componentEnabled" -}}
{{- $component := .component -}}
{{- $enabled := false -}}
{{- if eq $component "otel-collector" -}}
  {{- $enabled = .Values.global.otel.enabled -}}
{{- else if eq $component "ingestion-worker" -}}
  {{- $enabled = .Values.ingestionWorker.enabled -}}
{{- else if eq $component "open-terminal" -}}
  {{- $enabled = .Values.openTerminal.enabled -}}
{{- else if eq $component "postgres" -}}
  {{- $enabled = and .Values.postgres.enabled (eq .Values.postgres.mode "standalone") -}}
{{- else -}}
  {{- $enabled = (index .Values $component).enabled -}}
{{- end -}}
{{- if $enabled -}}true{{- end -}}
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
{{- $merged = mergeOverwrite $merged (deepCopy .) }}
{{- end }}
{{- with .componentAnnotations }}
{{- $merged = mergeOverwrite $merged (deepCopy .) }}
{{- end }}
{{- toYaml $merged }}
{{- end }}

{{/*
Topology spread constraints for prod multi-replica deployments.
"autoscaling" is the string result of "ai-stack.autoscalingEnabled"
("true" / ""); a map or bool is also tolerated for robustness.
*/}}
{{- define "ai-stack.topologySpread" -}}
{{- $asEnabled := false -}}
{{- if kindIs "string" .autoscaling -}}
{{- $asEnabled = (ne .autoscaling "") -}}
{{- else if kindIs "map" .autoscaling -}}
{{- $asEnabled = (default false (index .autoscaling "enabled")) -}}
{{- else -}}
{{- $asEnabled = (.autoscaling | default false) -}}
{{- end -}}
{{- $multiReplica := or (gt (int (.replicaCount | default 1)) 1) $asEnabled -}}
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
Resolve a generated credential so it stays stable across `helm upgrade`.
Precedence: explicit override > value already stored in the live Secret >
a freshly generated random value (first install / `helm template`).
Returns a base64-encoded string ready to place under a Secret `data:` key.
Usage:
  {{ include "ai-stack.persistentSecret" (dict "ctx" . "name" "<secret-name>" "key" "<data-key>" "override" <override-or-empty> "length" 48) }}
*/}}
{{- define "ai-stack.persistentSecret" -}}
{{- $override := .override | default "" -}}
{{- if $override -}}
{{- $override | b64enc -}}
{{- else -}}
{{- $existing := (lookup "v1" "Secret" .ctx.Release.Namespace .name) -}}
{{- if and $existing $existing.data (hasKey $existing.data .key) -}}
{{- index $existing.data .key -}}
{{- else -}}
{{- randAlphaNum (.length | default 48 | int) | b64enc -}}
{{- end -}}
{{- end -}}
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
Construct OPENAI_API_BASE_URLS: Ollama endpoint + external provider URLs.
*/}}
{{- define "ai-stack.openaiBaseUrls" -}}
{{- $urls := list -}}
{{- if .Values.ollama.enabled -}}
  {{- $urls = append $urls (printf "http://%s:%v" (include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "ollama")) (.Values.ollama.service.port | toString)) -}}
{{- end -}}
{{- if and .Values.externalAPIs.enabled .Values.externalAPIs.providers -}}
  {{- range .Values.externalAPIs.providers -}}
    {{- $urls = append $urls .baseUrl -}}
  {{- end -}}
{{- end -}}
{{- if and .Values.pydanticai.enabled .Values.pydanticai.exposeToOpenWebUI -}}
  {{- $urls = append $urls (printf "http://%s:%v/v1" (include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "pydanticai")) (.Values.pydanticai.service.port | toString)) -}}
{{- end -}}
{{- join ";" $urls -}}
{{- end }}

{{/*
Construct OPENAI_API_KEYS: placeholder for Ollama + secret refs for external providers.
*/}}
{{- define "ai-stack.openaiApiKeys" -}}
{{- $keys := list -}}
{{- if .Values.ollama.enabled -}}
  {{- $keys = append $keys "0" -}}
{{- end -}}
{{- if and .Values.externalAPIs.enabled .Values.externalAPIs.providers -}}
  {{- range $i, $p := .Values.externalAPIs.providers -}}
    {{- $keys = append $keys (printf "$(_EXTAPI_KEY_%d)" $i) -}}
  {{- end -}}
{{- end -}}
{{- if and .Values.pydanticai.enabled .Values.pydanticai.exposeToOpenWebUI -}}
  {{- $keys = append $keys "$(_PYDANTICAI_KEY)" -}}
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
Open WebUI high-availability environment.

Open WebUI is stateless ONLY when its session/config state lives in shared
backends. This injects, as production best practice (docs.openwebui.com
"Scaling & HA"):
  * WEBUI_SECRET_KEY (+ OAUTH_SESSION_TOKEN_ENCRYPTION_KEY) from the generated
    Secret so sessions survive restarts and are valid on every replica;
  * DATABASE_URL -> shared PostgreSQL (its own `openwebui` database) when
    postgres is enabled, replacing the single-pod SQLite file;
  * REDIS_URL + WEBSOCKET_MANAGER=redis + WEBSOCKET_REDIS_URL + websocket
    support -> Valkey, so multi-replica websocket/config state is coordinated.
The _PG_PASSWORD anchor (consumed by DATABASE_URL via $(...) substitution) is
injected only when postgres is enabled.
Usage: {{ include "ai-stack.webuiHaEnv" . | nindent N }}
*/}}
{{- define "ai-stack.webuiHaEnv" -}}
- name: WEBUI_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "openwebui") }}-secret
      key: secret-key
- name: OAUTH_SESSION_TOKEN_ENCRYPTION_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "openwebui") }}-secret
      key: secret-key
{{- if .Values.postgres.enabled }}
- name: _PG_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "ai-stack.postgresSecretName" . }}
      key: {{ include "ai-stack.postgresSecretKey" . }}
- name: DATABASE_URL
  value: {{ printf "postgresql://%s:$(_PG_PASSWORD)@%s:%s/%s?sslmode=%s" .Values.postgres.user (include "ai-stack.postgresHost" .) (include "ai-stack.postgresPort" .) .Values.openwebui.databaseName (include "ai-stack.postgresSslMode" .) | quote }}
{{- end }}
{{- if .Values.valkey.enabled }}
{{- $valkey := printf "redis://%s:%v/0" (include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "valkey")) .Values.valkey.service.port }}
- name: REDIS_URL
  value: {{ $valkey | quote }}
- name: WEBSOCKET_MANAGER
  value: "redis"
- name: WEBSOCKET_REDIS_URL
  value: {{ printf "redis://%s:%v/1" (include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "valkey")) .Values.valkey.service.port | quote }}
{{- /* ENABLE_WEBSOCKET_SUPPORT is set unconditionally in openwebui.env */}}
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
Ingress resource template (shared by openwebui, langgraph, etc.).
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
Gateway API HTTPRoute (gateway.networking.k8s.io/v1, GA since Gateway API v1.0).
Opt-in modern alternative to the Ingress resource for clusters running a
Gateway API implementation (e.g. Envoy Gateway, the chart's reference edge).
The chart emits only the per-app HTTPRoute and attaches it to a pre-existing
Gateway via parentRefs — mirroring how the Ingress path relies on an external
IngressClass/controller rather than provisioning one.
Usage:
  {{ include "ai-stack.httpRoute" (dict "root" . "component" "openwebui" "httpRoute" .Values.openwebui.httpRoute "servicePort" .Values.openwebui.service.port) }}
*/}}
{{- define "ai-stack.httpRoute" -}}
{{- if .httpRoute.enabled }}
{{- if not .httpRoute.parentRefs }}
{{- fail (printf "%s.httpRoute.enabled=true requires at least one httpRoute.parentRefs entry (the Gateway to attach to)" .component) }}
{{- end }}
{{- $defaultNs := .root.Values.global.gateway.namespace | default .root.Values.global.ingressNamespace }}
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: {{ include "ai-stack.componentName" (dict "Release" .root.Release "Chart" .root.Chart "component" .component) }}
  labels:
    {{- include "ai-stack.labels" .root | nindent 4 }}
  {{- with .httpRoute.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  parentRefs:
    {{- range .httpRoute.parentRefs }}
    - name: {{ required "httpRoute.parentRefs[].name is required (the Gateway name)" .name }}
      namespace: {{ .namespace | default $defaultNs | quote }}
      {{- with .sectionName }}
      sectionName: {{ . | quote }}
      {{- end }}
      {{- with .port }}
      port: {{ . }}
      {{- end }}
    {{- end }}
  {{- with .httpRoute.hostnames }}
  hostnames:
    {{- range . }}
    - {{ . | quote }}
    {{- end }}
  {{- end }}
  rules:
    {{- if .httpRoute.rules }}
    {{- toYaml .httpRoute.rules | nindent 4 }}
    {{- else }}
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: {{ include "ai-stack.componentName" (dict "Release" .root.Release "Chart" .root.Chart "component" .component) }}
          port: {{ .servicePort }}
    {{- end }}
{{- end }}
{{- end }}

{{/*
Resolve the CORS allowed-origins for Open Terminal. Never returns "*": a
wildcard CORS policy on a code-executing service is an OWASP A05
misconfiguration. Precedence:
  1. explicit openTerminal.corsAllowedOrigins
  2. legacy openTerminal.env.OPEN_TERMINAL_CORS_ALLOWED_ORIGINS (pre-2.6.0
     installs that set the old env knob keep their value — except a carried-over
     "*" from the old default, which is dropped so a `helm upgrade
     --reuse-values` does not retain a wildcard CORS policy)
  3. derived Open WebUI browser origin(s): ingress hosts (https when the host
     is TLS-covered, including a matching wildcard cert, else http) and httpRoute
     hostnames (http when a parentRef targets port 80, else https)
  4. the in-cluster Open WebUI Service origin (safe fallback)
CORS is only exercised when the terminal/notebook UI is exposed to a browser;
the default topology reaches Open Terminal server-side. For any non-standard
exposure, set openTerminal.corsAllowedOrigins explicitly.
Usage: {{ include "ai-stack.openTerminalCorsOrigins" . }}
*/}}
{{- define "ai-stack.openTerminalCorsOrigins" -}}
{{- $legacy := "" -}}
{{- with .Values.openTerminal.env -}}
{{- $legacy = (index . "OPEN_TERMINAL_CORS_ALLOWED_ORIGINS") | default "" -}}
{{- end -}}
{{- /* drop a carried-over "*" old default (reuse-values upgrade safety) */ -}}
{{- if eq (trim $legacy) "*" -}}{{- $legacy = "" -}}{{- end -}}
{{- if .Values.openTerminal.corsAllowedOrigins -}}
{{- .Values.openTerminal.corsAllowedOrigins -}}
{{- else if $legacy -}}
{{- $legacy -}}
{{- else -}}
{{- $origins := list -}}
{{- if .Values.openwebui.ingress.enabled -}}
{{- $tlsHosts := list -}}
{{- range .Values.openwebui.ingress.tls -}}
{{- range .hosts -}}
{{- $tlsHosts = append $tlsHosts . -}}
{{- end -}}
{{- end -}}
{{- range .Values.openwebui.ingress.hosts -}}
{{- $host := .host -}}
{{- $covered := has $host $tlsHosts -}}
{{- if not $covered -}}
{{- range $tlsHosts -}}
{{- if hasPrefix "*." . -}}
{{- $needle := printf ".%s" (trimPrefix "*." .) -}}
{{- if and (hasSuffix $needle $host) (not (contains "." (trimSuffix $needle $host))) -}}
{{- $covered = true -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- $scheme := ternary "https" "http" $covered -}}
{{- $origins = append $origins (printf "%s://%s" $scheme $host) -}}
{{- end -}}
{{- end -}}
{{- if .Values.openwebui.httpRoute.enabled -}}
{{- $httpListener := false -}}
{{- range .Values.openwebui.httpRoute.parentRefs -}}
{{- if eq (.port | default 0 | int) 80 -}}
{{- $httpListener = true -}}
{{- end -}}
{{- end -}}
{{- $scheme := ternary "http" "https" $httpListener -}}
{{- range .Values.openwebui.httpRoute.hostnames -}}
{{- $origins = append $origins (printf "%s://%s" $scheme .) -}}
{{- end -}}
{{- end -}}
{{- if $origins -}}
{{- join "," $origins -}}
{{- else -}}
{{- printf "http://%s:%v" (include "ai-stack.componentName" (dict "Release" .Release "Chart" .Chart "component" "openwebui")) .Values.openwebui.service.port -}}
{{- end -}}
{{- end -}}
{{- end }}

{{/*
ArgoCD sync-wave annotation for a tier. A fresh `argocd app sync` then rolls out
in dependency order: foundation (Secrets + ServiceAccounts) → platform
(datastores, backing services, infra — the default wave) → app (workloads that
consume them) → policy (HPA/PDB, applied last so their target workloads already
exist, avoiding a wave deadlock where a policy never reconciles). Harmless
outside ArgoCD (it is just a metadata annotation).
Usage inside a metadata.annotations block:
  {{- include "ai-stack.syncWave" "app" | nindent 4 }}
*/}}
{{- define "ai-stack.syncWave" -}}
{{- $waves := dict "foundation" "-10" "platform" "0" "app" "5" "policy" "10" -}}
argocd.argoproj.io/sync-wave: {{ index $waves . | default "0" | quote }}
{{- end }}

