import functools
import hashlib
import json
import os
import pdb
import shutil
import uuid
from datetime import datetime, timezone
from enum import Enum
from hmac import digest

from flask import Flask, request, jsonify

app = Flask(__name__)


upload_sessions = {}


class UploadState:
    def __init__(self, session_id, name):
        self.session_id = session_id
        self.name = name
        self.uploaded_data = b""
        self.bytes_received = 0
        self.created_at = datetime.now(timezone.utc)


class Error(Enum):
    BLOB_UNKNOWN = ('BLOB_UNKNOWN', 404)
    BLOB_UPLOAD_INVALID = ('BLOB_UPLOAD_INVALID', 400)
    BLOB_UPLOAD_CHUNK_OUT_OF_ORDER = ('BLOB_UPLOAD_INVALID', 416)
    BLOB_UPLOAD_UNKNOWN = ('BLOB_UPLOAD_UNKNOWN', 404)
    DIGEST_INVALID = ('DIGEST_INVALID', 400)
    MANIFEST_BLOB_UNKNOWN = ('MANIFEST_BLOB_UNKNOWN', 404)
    MANIFEST_INVALID = ('MANIFEST_INVALID', 400)
    MANIFEST_UNKNOWN = ('MANIFEST_UNKNOWN', 404)
    NAME_INVALID = ('NAME_INVALID', 400)
    NAME_UNKNOWN = ('NAME_UNKNOWN', 404)
    SIZE_INVALID = ('SIZE_INVALID', 400)
    UNAUTHORIZED = ('UNAUTHORIZED', 401)
    DENIED = ('DENIED', 403)
    UNSUPPORTED = ('UNSUPPORTED', 415)
    TOOMANYREQUESTS = ('TOOMANYREQUESTS', 429)


def error_response(error_key, message='', detail=''):
    error_code, error_status = error_key.value
    error_body = {
        "errors": [
            {
                "code": error_code,
                "message": message,
                "detail": detail
            }
        ]
    }
    return jsonify(error_body), error_status

# example users to test authentication
users = {
    "username": "password"
}

def authenticate():
    return "Login required", 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}

def check_auth(username, password):
    return users.get(username) == password

def requires_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


# end-1
@app.route('/v2/', methods=['GET'])
@requires_auth
def verify_specification_implementation():
    return '', 200


# end-2
@app.route('/v2/<path:name>/blobs/<digest>/', methods=['GET', 'HEAD'])
@requires_auth
def get_blob_by_digest(name, digest):
    file_content = find_file_bytes(f'blobs/{name}', f'{digest}')
    if file_content is None:
        return error_response(Error.BLOB_UNKNOWN, message="Could not find blob with specified digest", detail=str({
            'name': name,
            'digest': digest
        }))

    if request.method == 'HEAD':
        return '', 200, {
            'Docker-Content-Digest': digest,
            'Content-Length': len(file_content)
        }

    return file_content, 200, {'Docker-Content-Digest': digest}

# end-3 HEAD
@app.route('/v2/<path:name>/manifests/<reference>/', methods=['HEAD'])
@requires_auth
def get_manifest_checksum(name, reference):
    if is_valid_digest(reference):
        # reference is a digest
        digest_content = find_file_bytes(f'manifests/{name}', reference)
    else:
        # reference is a tag
        digest_content = find_file_bytes(f'manifests/{name}/{reference}', 'manifest.sha256')

    if digest_content is None:
        tag = find_tag_by_digest(name, reference)
        if tag is None:
            return error_response(Error.MANIFEST_UNKNOWN, message="Could not find a manifest with specified reference", detail=str({'name': name, 'reference': reference}))

        digest_content = find_file_bytes(f'manifests/{name}/{tag}', 'manifest.sha256')
        if digest_content is None:
            return error_response(Error.MANIFEST_UNKNOWN, message="Could not find a manifest with specified reference", detail=str({'name': name, 'reference': reference}))

    digest = reference if is_valid_digest(reference) else digest_content.decode('utf-8')

    return '', 200, {
        'Docker-Content-Digest': digest,
        'Content-Length': len(digest_content)
    }


# end-3 GET
@app.route('/v2/<path:name>/manifests/<reference>/', methods=['GET'])
@requires_auth
def get_manifest(name, reference):
    if is_valid_digest(reference):
        # reference is a digest
        manifest_content = find_file_bytes(f'manifests/{name}', f'{reference}')
    else:
        # reference is a tag
        manifest_content = find_file_bytes(f'manifests/{name}/{reference}', 'manifest')

    if manifest_content is None:
        tag = find_tag_by_digest(name, reference)
        if tag is None:
            return error_response(Error.MANIFEST_UNKNOWN, message="Could not find a manifest with specified reference", detail=str({'name': name, 'reference': reference}))

        manifest_content = find_file_bytes(f'manifests/{name}/{tag}', 'manifest')
        if manifest_content is None:
            return error_response(Error.MANIFEST_UNKNOWN, message="Could not find a manifest with specified reference", detail=str({'name': name, 'reference': reference}))

    return manifest_content, 200, {
        'Content-Type': 'application/vnd.docker.distribution.manifest.v2+json',
        'Content-Length': len(manifest_content),
        'Docker-Content-Digest': reference,
        'Etag': f'"{reference}"'
    }


# end-4ab, end-11
@app.route('/v2/<path:name>/blobs/uploads/', methods=['POST'])
@requires_auth
def initiate_blob_upload(name):
    digest = request.args.get('digest')
    if not digest:
        session_id = str(uuid.uuid4())

        # add to active sessions
        upload_sessions[session_id] = UploadState(session_id, name)
        print("Upload session created: ", session_id)

        upload_location = f'/v2/{name}/blobs/uploads/{session_id}/'

        return '', 202, {'Location': upload_location}

    if request.content_length is None or request.content_type != 'application/octet-stream':
        return error_response(Error.BLOB_UPLOAD_INVALID, message="Request does not contain Content-Length or Content-Type is not 'application/octet-stream'", detail=str({
            'name': name,
            'digest': digest
        }))

    mount = request.args.get('mount')
    from_chunk = request.args.get('from')
    if mount or from_chunk:
        # end-11
        return '', 202

    # end-4b
    binary_blob = request.data
    save_file(f'blobs/{name}', f'{digest}', binary_blob)

    return '', 202, {'Location': f'/v2/{name}/blobs/{digest}/'}


# end-5, Undocumented Stream Blob Upload - https://github.com/opencontainers/distribution-spec/issues/303
@app.route('/v2/<path:name>/blobs/uploads/<session_id>/', methods=['PATCH'])
@requires_auth
def upload_blob_stream_part(name, session_id):
    if session_id not in upload_sessions:
        return error_response(Error.BLOB_UPLOAD_UNKNOWN, message="Upload session not found", detail=str({'session_id': session_id}))

    if request.content_type != 'application/octet-stream':
        return error_response(Error.BLOB_UPLOAD_INVALID, message="Request does not contain Content-Length or Content-Type is not 'application/octet-stream'", detail=str({
            'name': name,
            'session_id': session_id
        }))

    binary_blob = request.data

    upload_session = upload_sessions[session_id]

    content_range = request.headers.get('Content-Range')
    # handle blob chunks uploading (end-5)
    if content_range:
        try:
            start, end = map(int, content_range.split('-'))

            if start != upload_session.bytes_received:
                return error_response(Error.BLOB_UPLOAD_CHUNK_OUT_OF_ORDER, message="Chunk uploaded out of order", detail=str({
                    'expected_start': upload_session.bytes_received,
                    'received_start': start,
                    'session_id': session_id
                }))

            # append chunk to the session data
            upload_session.uploaded_data += binary_blob
            upload_session.bytes_received += len(binary_blob)

            print(f"Added bytes to chunk with session id {session_id}: {upload_session.bytes_received}")

            return '', 202, {
                'Location': f'/v2/{name}/blobs/uploads/{session_id}/',
                'Range': f'0-{upload_session.bytes_received - 1}'
            }
        except ValueError:
            return error_response(Error.BLOB_UPLOAD_INVALID, message="Invalid Content-Range format", detail=str({
                'content_range': content_range,
                'session_id': session_id
            }))

    # handle blob stream uploading
    try:
        # Read the entire binary data from the request
        binary_blob = request.get_data()

        # Append the stream to session data
        upload_session.uploaded_data += binary_blob
        upload_session.bytes_received += len(binary_blob)

        print(f"Stream uploaded for session {session_id}: {upload_session.bytes_received} bytes received")

        # Return a successful response with location and range
        return '', 202, {
            'Location': f'/v2/{name}/blobs/uploads/{session_id}/',
            'Range': f'0-{upload_session.bytes_received - 1}'
        }
    except OSError as e:
        return error_response(Error.BLOB_UPLOAD_INVALID, message="Failed to read stream data", detail=str({
            'error': str(e),
            'session_id': session_id
        }))


# end-6
@app.route('/v2/<path:name>/blobs/uploads/<session_id>/', methods=['PUT'])
@requires_auth
def finalize_blob_upload(name, session_id):
    if session_id not in upload_sessions:
        return error_response(Error.BLOB_UPLOAD_UNKNOWN, message="Upload session not found", detail=str({'session_id': session_id}))

    # check if the request contains a digest
    digest = request.args.get('digest')
    if not digest:
        return error_response(Error.BLOB_UPLOAD_INVALID, message="Request does not have 'digest' query parameter", detail=str({
            'name': name,
            'session_id': session_id
        }))

    binary_blob = request.data

    upload_session = upload_sessions[session_id]

    # check if the request contains a blob
    if binary_blob:
        upload_session.uploaded_data += binary_blob

    save_file(f'blobs/{name}', f'{digest}', upload_session.uploaded_data)

    print(f"Blob upload session finalized: {session_id}")

    del upload_sessions[session_id]

    return '', 201, {
        'Location': f'/v2/{name}/blobs/{digest}/'
    }


# end-7
@app.route("/v2/<path:name>/manifests/<reference>/", methods=['PUT'])
@requires_auth
def put_manifest(name, reference):
    if request.content_type != 'application/vnd.oci.image.manifest.v1+json' and request.content_type != 'application/vnd.docker.distribution.manifest.v2+json':
        return error_response(Error.MANIFEST_INVALID, message="Content-Type is invalid", detail=str({
            'name': name,
            'digest': reference
        }))

    manifest = request.get_json()
    if manifest is None:
        return error_response(Error.MANIFEST_INVALID, message="Request does not contain a valid JSON object", detail=str({
            'name': name,
            'digest': reference
        }))

    if is_valid_digest(reference):
        # save manifest
        save_file(f'manifests/{name}', reference, request.data)

        content_digest = reference
    else:
        tag_digest = calculate_digest_from_bytes(request.data)

        # save manifest
        save_file(f'manifests/{name}/{reference}', 'manifest', request.data)

        # save manifest digest
        save_file(f'manifests/{name}/{reference}', f'manifest.sha256', tag_digest.encode('utf-8'))

        content_digest = tag_digest


    return '', 201, {
        'Location': f'/v2/{name}/manifests/{content_digest}/',
        'Docker-Content-Digest': content_digest
    }


# end-8ab
@app.route('/v2/<path:name>/tags/list/', methods=['GET'])
@requires_auth
def get_tags_list(name):
    last_tag = request.args.get('last')
    amount = request.args.get('n')
    if not amount or not last_tag:
        # end-8a


        return '', 200

    # end-8b
    return '', 200


# end-9
@app.route('/v2/<path:name>/manifests/<reference>/', methods=['DELETE'])
def delete_manifest_by_reference(name, reference):
    manifest_path = f'manifests/{name}/{reference}'
    if os.path.exists(manifest_path):
        delete_file(manifest_path)
        return '', 202

    tag = find_tag_by_digest(name, reference)
    if tag:
        delete_file(f'manifests/{name}/{tag}')
        return '', 202

    return error_response(Error.MANIFEST_UNKNOWN, message="Could not find a manifest with specified reference", detail=str({
        'name': name,
        'reference': reference
    }))


# end-10
@app.route('/v2/<path:name>/blobs/<digest>/', methods=['DELETE'])
@requires_auth
def delete_blob_by_digest(name, digest):
    file_path = os.path.join(f'blobs/{name}', f'{digest}')
    if os.path.exists(file_path):
        os.remove(file_path)
        return '', 202
    return error_response(Error.BLOB_UNKNOWN, message="Could not find a blob with specified digest", detail=str({
        'name': name,
        'digest': digest
    }))


# end-12ab
@app.route('/v2/<path:name>/referrers/<digest>/', methods=['GET'])
@requires_auth
def get_referrers(name, digest):
    artifact_type = request.args.get('artifactType')
    if artifact_type:
        # end-12b
        return '', 200

    # end-12a


    return '', 200


# end-13
@app.route('/v2/<path:name>/blobs/uploads/<session_id>/', methods=['GET'])
@requires_auth
def get_blob_upload_status(name, session_id):
    if session_id not in upload_sessions:
        return error_response(Error.BLOB_UPLOAD_UNKNOWN, message="Upload session not found", detail=str({'session_id': session_id}))

    upload_session = upload_sessions[session_id]

    bytes_received = upload_session.bytes_received

    return '', 204, {
        'Location': f'/v2/{name}/blobs/uploads/{session_id}/',
        'Range': f'0-{bytes_received - 1}'
    }


def save_file(directory, filename, data, append=False):
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
        sanitized_filename = filename.replace('/', '_')
        file_path = os.path.join(directory, sanitized_filename)
        mode = 'ab' if append else 'wb'
        with open(file_path, mode) as f:
            f.write(data)
        print(f"File saved successfully: {file_path}")
    except Exception as e:
        print(f"Error saving file: {e}")


def find_file_bytes(directory, filename):
    file_path = os.path.join(directory, filename)
    if os.path.exists(file_path):
        with open(file_path, 'rb') as file:
            return file.read()
    return None


def delete_file(file_path):
    try:
        if not os.path.exists(file_path):
            return

        if os.path.isfile(file_path):
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)
            print(f"Deleted directory and its contents: {file_path}")
        else:
            print(f"File not found: {file_path}")
    except Exception as e:
        print(f"Error deleting file {file_path}: {str(e)}")


def find_tag_by_digest(name, digest):
    tags_dir = f'manifests/{name}'

    for tag in os.listdir(tags_dir):
        sha256_file = f'{tags_dir}/{tag}/manifest.sha256'

        if os.path.exists(sha256_file):
            with open(sha256_file, 'r') as f:
                stored_digest = f.read().strip()

            if stored_digest == digest:
                return tag

    return None


def get_file_size(file_path):
    return os.path.getsize(file_path) if os.path.exists(file_path) else 0


def calculate_digest_from_file(file_path) -> str:
    sha256_hash = hashlib.sha256()

    with open(file_path, 'rb') as f:
        file_content = f.read()
        sha256_hash.update(file_content)

    return f'sha256:{sha256_hash.hexdigest()}'


def calculate_digest_from_bytes(data) -> str:
    sha256_hash = hashlib.sha256()
    sha256_hash.update(data)
    return f'sha256:{sha256_hash.hexdigest()}'


def is_valid_digest(digest):
    return digest.startswith('sha256:')


# https://github.com/opencontainers/distribution-spec/blob/main/spec.md
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
