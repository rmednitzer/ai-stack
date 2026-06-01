# Apache Tika

Document text-extraction service. Called by Open WebUI, LangGraph, and the ingestion worker to turn PDFs, Office documents, and images into text suitable for embedding and retrieval.

- **Tier**: T2 (productivity)
- **Boundary**: `ingestion`
- **Control refs**: [CTL-002](../governance/CONTROLS.md#controls-ctl), [POL-001](../governance/CONTROLS.md#policies-pol)
- **Default**: enabled
- **Upstream**: <https://tika.apache.org/> · [REST API](https://tika.apache.org/3.3.1/formats.html)
- **Default image**: `apache/tika` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/tika/`](../../templates/tika/)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `tika.enabled` | Toggle the component |
| `tika.image.{repository,tag}` | Container image override |
| `tika.resources` | CPU / memory; PDF OCR can be CPU-heavy |
| `tika.service.port` | Service port (default 9998) |

## Security

- Stateless, read-only root filesystem enforced
- No persistent storage; documents stream through
- Dedicated ServiceAccount, `automountServiceAccountToken: false`

## Related HOWTO sections

- [§4 RAG — Upload documents](../../HOWTO.md#41-upload-documents-via-the-ui)
- [§5 Async Document Ingestion](../../HOWTO.md#5-async-document-ingestion)
