# oci-repository-prototype

## Conformance Status
38/74 Passed

## Storage
All objects are stored as files in separate directories, each type has its own directory with namespace in it. Blobs and manifests are identified by digest.
- blobs - `/blobs/<namespace>`
- manifests - `/manifests/<namespace>`
- tags - `/tags/<namespace>`

## Sessions

