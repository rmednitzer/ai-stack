# Contributing to ai-stack

Thank you for considering contributing to the ai-stack Helm chart.

## Development Setup

1. Install prerequisites:
   - [Helm](https://helm.sh/docs/intro/install/) 3.12+
   - [helm-docs](https://github.com/norwoodj/helm-docs) (optional, for README generation)
   - [chart-testing (ct)](https://github.com/helm/chart-testing) (optional, for CI-grade linting)
   - [kubectl](https://kubernetes.io/docs/tasks/tools/) with access to a test cluster

2. Clone the repository:

   ```bash
   git clone https://github.com/rmednitzer/ai-stack.git
   cd ai-stack
   ```

3. Lint your changes:

   ```bash
   helm lint .
   helm lint . -f values.yaml -f values-prod.yaml
   ```

4. Dry-run to verify rendering:

   ```bash
   helm template ai-stack . --debug
   ```

## Pull Request Process

1. Create a feature branch from `main`.
2. Make your changes, ensuring:
   - `helm lint .` passes with no errors or warnings.
   - `helm template ai-stack . --debug` renders without errors.
   - All new values are documented in `values.yaml` with `# --` comment annotations.
   - Security contexts follow the PSA restricted baseline (non-root, read-only FS where possible, drop all capabilities).
   - NetworkPolicy rules are added for any new component.
3. Update `Chart.yaml` version following [SemVer](https://semver.org/).
4. Open a pull request with a clear description of the change.

## Guidelines

- **Security first**: Every new component must have a dedicated ServiceAccount, NetworkPolicy rules, and appropriate securityContext.
- **Conditional deployment**: All components must be gated behind an `enabled` flag.
- **Consistent naming**: Use `ai-stack.componentName` helper for all resource names.
- **Governance labels**: Apply `assurance.platform/tier` and `assurance.platform/boundary` annotations to all new deployments.
- **No hardcoded secrets**: Use auto-generated secrets or external secret store references.
