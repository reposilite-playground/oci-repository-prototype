import json
import os
import pdb
import uuid
from enum import Enum

from flask import Flask, request, jsonify

app = Flask(__name__)

class Error(Enum):
    BLOB_UNKNOWN = ('BLOB_UNKNOWN', 404)
    BLOB_UPLOAD_INVALID = ('BLOB_UPLOAD_INVALID', 400)
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


# end-1
@app.route('/v2/', methods=['GET'])
def verify_specification_implementation():
    return '', 200


# end-2
@app.route('/v2/<path:name>/blobs/<digest>/', methods=['GET', 'HEAD'])
def get_blob_by_digest(name, digest):
    file_content = find_file(f'blobs/{name}', f'{digest}')
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


# end-3
@app.route('/v2/<path:name>/manifests/<digest>/', methods=['GET', 'HEAD'])
def get_manifest_by_digest(name, digest):
    file_content = find_file(f'manifests/{digest}', f'{digest}')
    if file_content is None:
        return error_response(Error.MANIFEST_UNKNOWN, message="Could not find manifest with specified digest", detail=str({
            'name': name,
            'digest': digest
        }))

    breakpoint()

    if request.method == 'HEAD':
        return '', 200, {
            'Docker-Content-Digest': digest,
            'Content-Length': len(file_content)
        }

    return file_content, 200, {'Docker-Content-Digest': digest}


# end-4ab, end-11
@app.route('/v2/<path:name>/blobs/uploads/', methods=['POST'])
def upload_blob(name):
    digest = request.args.get('digest')
    if not digest:
        session_id = str(uuid.uuid4())
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


# Undocumented Stream Blob Upload - https://github.com/opencontainers/distribution-spec/issues/303
@app.route('/v2/<path:name>/blobs/uploads/<session_id>/', methods=['PATCH'])
def upload_blob_chunk(name, session_id):
    if request.content_length is None or request.content_type != 'application/octet-stream':
        return error_response(Error.BLOB_UPLOAD_INVALID, message="Request does not contain Content-Length or Content-Type is not 'application/octet-stream'", detail=str({
            'name': name,
            'session_id': session_id
        }))

    binary_blob = request.data

    save_file(f'blobs/{name}', f'{session_id}', binary_blob, append=True)

    return '', 202, {
        'Location': f'/v2/{name}/blobs/uploads/{session_id}/'
    }


# end-6
@app.route('/v2/<path:name>/blobs/uploads/<location>/', methods=['PUT'])
def upload_blob_to_obtained_location(name, location):
    # check if the request contains the required headers
    if not request.content_length or request.content_type != 'application/octet-stream':
        return error_response(Error.BLOB_UPLOAD_INVALID, message="Request does not contain Content-Length or Content-Type is not 'application/octet-stream'", detail=str({
            'name': name,
            'Location': location
        }))

    # check if the request contains a digest
    digest = request.args.get('digest')
    if not digest:
        return error_response(Error.BLOB_UPLOAD_INVALID, message="Request does not have 'digest' query parameter", detail=str({
            'name': name,
            'Location': location
        }))

    binary_blob = request.data

    # check if the request contains a blob
    if not binary_blob:
        return error_response(Error.BLOB_UPLOAD_INVALID, message="Request does not have any body content", detail=str({
            'name': name,
            'Location': location,
            'digest': digest
        }))

    save_file(f'blobs/{name}', f'{digest}', binary_blob, append=True)

    return '', 201, {
        'Location': f'/v2/{name}/blobs/{digest}/'
    }


# end-7
@app.route("/v2/<path:name>/manifests/<digest>/", methods=['PUT'])
def put_manifest(name, digest):
    if request.content_type != 'application/vnd.oci.image.manifest.v1+json':
        return error_response(Error.MANIFEST_INVALID, message="Content-Type must be 'application/vnd.oci.image.manifest.v1+json'", detail=str({
            'name': name,
            'digest': digest
        }))

    manifest = request.get_json()
    if manifest is None:
        return error_response(Error.MANIFEST_INVALID, message="Request does not contain a valid JSON object", detail=str({
            'name': name,
            'digest': digest
        }))

    save_file(f'manifests/{name}', f'{digest}', request.data)

    digest = f"{uuid.uuid4().hex}"

    return '', 201, {
        'Location': f'/v2/{name}/manifests/{digest}/',
        'Docker-Content-Digest': digest
    }


# end-8ab
@app.route('/v2/<path:name>/tags/list/', methods=['GET'])
def get_tags_list(name):
    last_tag = request.args.get('last')
    amount = request.args.get('n')
    if not amount or not last_tag:
        # end-8b
        return '', 200

    # end-8a
    return '', 200


# end-9
@app.route('/v2/<path:name>/manifests/<digest>/', methods=['DELETE'])
def delete_manifest_by_reference(name, digest):
    file_path = os.path.join(f'manifests/{name}', f'{digest}')
    if os.path.exists(file_path):
        os.remove(file_path)
        return '', 202
    return error_response(Error.MANIFEST_UNKNOWN, message="Could not find a manifest with specified digest", detail=str({
        'name': name,
        'digest': digest
    }))


# end-10
@app.route('/v2/<path:name>/blobs/<digest>/', methods=['DELETE'])
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
def get_referrers(name, digest):
    artifact_type = request.args.get('artifactType')
    if artifact_type:
        # end-12b
        return '', 200

    # end-12a
    return '', 200


# end-13
@app.route('/v2/<path:name>/blobs/uploads/<location>/', methods=['GET'])
def get_blob_upload_status(name, location):
    file_path = os.path.join('blobs', location)
    if os.path.exists(file_path):
        file_size = get_file_size(file_path)
        return '', 204, {
            'Location': location + '/',
            'Range': f'0-{file_size - 1}'
        }
    return error_response(Error.BLOB_UPLOAD_UNKNOWN, message="Could not find uploading blob with specified location", detail=str({
        'name': name,
        'Location': location
    }))


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


def find_file(directory, filename):
    file_path = os.path.join(directory, filename)
    if os.path.exists(file_path):
        with open(file_path, 'rb') as file:
            return file.read()
    return None


def get_file_size(file_path):
    return os.path.getsize(file_path) if os.path.exists(file_path) else 0


# https://github.com/opencontainers/distribution-spec/blob/main/spec.md
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
