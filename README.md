# oci-repository-prototype
## Conformance Tests
65/74 tests passed
## Storage
All objects are stored as files in separate directories, each type has its own directory with namespace in it. Blobs and manifests are identified by digest. Digests are also used as checksums, so if a manifest is not tagged, it will have its file created in the `/manifests/<namespace>` directory, where the filename will be a digest, and the content will be the actual content of a manifest. However if there is a tagged manifest, it will store 2 separate files in `/manifests/<namespace>/tags/<tag>` directory.
- blobs - `/blobs/<namespace>`
- manifests - `/manifests/<namespace>/<digest>`
- tags
  - checksum - `/manifests/<namespace>/tags/<tag>/manifest.sha256`
  - content - `/manifests/<namespace>/tags/<tag>/manifest`
## Sessions

