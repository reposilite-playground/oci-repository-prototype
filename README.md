# oci-repository-prototype
This is a research prototype developed for Reposilite to evaluate what is needed and how much time it would take to implement OCI (Open Container Initiative) image repository functionality in Reposilite. The prototype supports pushing and pulling Docker images, including chunked uploads and streamed pushes.
## Conformance Tests
65 out of 74 tests have passed – pushing and pulling images are functional, making the prototype ready for basic use with minimal functionality.
## Storage
All objects are stored as files in separate directories, with each object type having its own 
designated directory based on its namespace. Blobs and manifests are identified by their digest,
which also serves as a checksum. If a manifest is untagged, its file is stored in the `/manifests/<namespace>` directory,
where the filename is the digest, and the content is the actual manifest data. For tagged manifests, 
two separate files are created in the `/manifests/<namespace>/tags/<tag>` directory.
- **Blobs:** `/blobs/<namespace>`
- **Manifests:** `/manifests/<namespace>/<digest>`
- **Tags:**
  - **Checksum:** `/manifests/<namespace>/tags/<tag>/manifest.sha256`
  - **Content:** `/manifests/<namespace>/tags/<tag>/manifest`
## Sessions
Upload sessions are managed in-memory, with each session object identified by a UUID. The structure of a session object is as follows:
```JSON
{
  "session_id": "UUID",
  "name": "string",
  "uploaded_data": "bytes",
  "bytes_received": "int",
  "created_at": "datetime"
}
```
This structure tracks the upload session's state, including the data received and the time of creation.
