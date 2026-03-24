## Description

<!-- Briefly describe the change and the motivation behind it. -->

Fixes # <!-- Link to the related issue, if applicable -->

## Type of Change

<!-- Check all that apply -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking addition of a new component or value)
- [ ] Breaking change (renamed/removed values, dropped Kubernetes version support)
- [ ] Security fix (vulnerability or hardening improvement)
- [ ] Documentation update
- [ ] Dependency update (image tag bump, GitHub Action version)

## Chart Version Bump

<!-- Per SemVer: PATCH for fixes/docs/image bumps, MINOR for new features, MAJOR for breaking changes -->

- [ ] `Chart.yaml` version updated

## Testing

<!-- Describe the testing you have performed -->

- [ ] `helm lint .` passes with no errors or warnings
- [ ] `helm lint . -f values.yaml -f values-prod.yaml` passes
- [ ] `helm template ai-stack . --debug` renders without errors
- [ ] `helm template ai-stack . -f values.yaml -f values-prod.yaml --debug` renders without errors

## Security Checklist

<!-- For any new or modified component -->

- [ ] SecurityContext set (`runAsNonRoot`, `allowPrivilegeEscalation: false`, `drop: [ALL]`, `seccompProfile: RuntimeDefault`)
- [ ] Dedicated ServiceAccount with `automountServiceAccountToken: false`
- [ ] NetworkPolicy ingress and egress rules defined
- [ ] No plaintext secrets in values or templates (auto-generated or `existingSecret` reference)
- [ ] Governance annotations applied (`assurance.platform/tier`, `assurance.platform/boundary`)
