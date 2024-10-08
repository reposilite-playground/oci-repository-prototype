import os
import uuid

from flask import Flask, request

app = Flask(__name__)


# end-1
@app.route('/v2/', methods=['GET'])
def verify_specification_implementation():
    return '', 200


# end-2
@app.route('/v2/<path:name>/blobs/<digest>/', methods=['GET', 'HEAD'])
def get_blob_by_digest(name, digest):
    file_content = find_blob_file('blobs', f'{name}_{digest}')
    if file_content is None:
        return '', 404

    if request.method == 'HEAD':
        return '', 200, {
            'Docker-Content-Digest': digest,
            'Content-Length': len(file_content)
        }

    return file_content, 200, {'Docker-Content-Digest': digest}


# end-3
@app.route('/v2/<path:name>/manifests/<location>/', methods=['GET', 'HEAD'])
def get_manifest_by_reference(name, location):
    file_content = find_blob_file('manifests', f'{name}_{location}')
    if file_content is None:
        return '', 404

    if request.method == 'HEAD':
        return '', 200, {
            'Docker-Content-Digest': location,
            'Content-Length': len(file_content)
        }

    return file_content, 200, {'Docker-Content-Digest': location}


# end-4ab, end-11
@app.route('/v2/<path:name>/blobs/uploads/', methods=['POST'])
def upload_blob(name):
    digest = request.args.get('digest')
    if not digest:
        session_id = str(uuid.uuid4())
        upload_location = f'/v2/{name}/blobs/uploads/{session_id}/'
        return '', 202, {'Location': upload_location}

    if request.content_length is None or request.content_type != 'application/octet-stream':
        return '', 400

    mount = request.args.get('mount')
    from_chunk = request.args.get('from')
    if mount or from_chunk:
        # end-11
        return '', 202

    # end-4b
    binary_blob = request.data
    save_blob_to_file('blobs', f'{name}_{digest}', binary_blob)

    return '', 202, {'Location': f'/v2/{name}/blobs/{digest}/'}


# Undocumented Stream Blob Upload - https://github.com/opencontainers/distribution-spec/issues/303
@app.route('/v2/<path:name>/blobs/uploads/<location>/', methods=['PATCH'])
def upload_blob_chunk(name, location):
    if request.content_length is None or request.content_type != 'application/octet-stream':
        return '', 400

    binary_blob = request.data

    save_blob_to_file('blobs', f'{name}_{location}', binary_blob, append=True)

    file_path = os.path.join('blobs', f'{name}_{location}')

    save_blob_to_file('blobs', f'{name}_{location}', binary_blob, append=True)

    get_file_size(file_path)
    return '', 202, {
        'Location': f'/v2/{name}/blobs/uploads/{location}/'
    }


# end-6
@app.route('/v2/<path:name>/blobs/uploads/<location>/', methods=['PUT'])
def close_blob_upload(name, location):
    digest = request.args.get('digest')
    if not digest:
        return '', 400

    file_path = os.path.join('blobs', f'{name}_{location}')

    if not os.path.exists(file_path):
        return '', 404

    binary_blob = request.data
    if binary_blob:
        save_blob_to_file('blobs', f'{name}_{location}', binary_blob, append=True)

    calculated_digest = f"{uuid.uuid4().hex}"

    if digest != calculated_digest:
        return '', 400

    return '', 201, {
        'Location': f'/v2/{name}/blobs/{digest}/'
    }


# end-7
@app.route("/v2/<path:name>/manifests/<location>/", methods=['PUT'])
def put_manifest(name, location):
    if request.content_type != 'application/vnd.oci.image.manifest.v1+json':
        return '', 400

    manifest = request.get_json()
    if manifest is None:
        return '', 400

    save_blob_to_file('manifests', f'{name}_{location}', request.data)

    digest = f"{uuid.uuid4().hex}"

    return '', 201, {
        'Location': f'/v2/{name}/manifests/{location}/',
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
@app.route('/v2/<path:name>/manifests/<location>/', methods=['DELETE'])
def delete_manifest_by_reference(name, location):
    file_path = os.path.join('manifests', f'{name}_{location}')
    if os.path.exists(file_path):
        os.remove(file_path)
        return '', 202
    return '', 404


# end-10
@app.route('/v2/<path:name>/blobs/<digest>/', methods=['DELETE'])
def delete_blob_by_digest(name, digest):
    file_path = os.path.join('blobs', f'{name}_{digest}')
    if os.path.exists(file_path):
        os.remove(file_path)
        return '', 202
    return '', 404


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
    return '', 404


def save_blob_to_file(directory, filename, data, append=False):
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


def find_blob_file(directory, filename):
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
