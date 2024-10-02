import os

from flask import Flask, request

app = Flask(__name__)


# end-1
@app.route('/v2', methods=['GET'])
def verify_specification_implementation():
    return '', 200


# end-2
@app.route('/v2/<name>/blobs/<digest>', methods=['GET', 'HEAD'])
def get_blob_by_digest(name, digest):
    file_content = find_blob_file('blobs', f'{name}_{digest}')
    if file_content is None:
        return '', 404
    return file_content, 200, {'Docker-Content-Digest': digest}


# end-3
@app.route('/v2/<name>/manifests/<reference>', methods=['GET', 'HEAD'])
def get_manifest_by_reference(name, reference):
    file_content = find_blob_file('manifests', f'{name}_{reference}')
    if file_content is None:
        return '', 404

    return file_content, 200, {'Docker-Content-Digest': reference}


# end-4ab, end-11
@app.route('/v2/<name>/blobs/uploads/', methods=['POST'])
def upload_blob(name):
    if request.content_length is None or request.content_type != 'application/octet-stream':
        return '', 400

    digest = request.args.get('digest')
    if not digest:
        # end-4a
        return '', 202

    mount = request.args.get('mount')
    from_chunk = request.args.get('from')
    if mount or from_chunk:
        # end-11
        return '', 202

    # end-4b
    binary_blob = request.data

    save_blob_to_file('blobs', f'{name}_{digest}', binary_blob)

    return '', 202, {'Location': f'/v2/{name}/blobs/{digest}'}


# end-5
@app.route('/v2/<name>/blobs/uploads/<reference>', methods=['PATCH'])
def upload_blob_chunk(name, reference):
    if request.content_length is None or request.content_type != 'application/octet-stream':
        return '', 400

    binary_blob = request.data

    save_blob_to_file('blobs', f'{name}_{reference}', binary_blob)

    return '', 202, {'Location': f'/v2/{name}/blobs/{reference}'}


# end-6
@app.route('/v2/<name>/blobs/uploads/<reference>', methods=['PUT'])
def upload_blob_chunk_end(name, reference):
    if request.content_length is None or request.content_type != 'application/octet-stream':
        return '', 400

    digest = request.args.get('digest')
    if not digest:
        return '', 400

    binary_blob = request.data

    save_blob_to_file('blobs', f'{name}_{digest}', binary_blob)

    return '', 202, {'Location': f'/v2/{name}/blobs/{digest}'}


# end-7
@app.route("/v2/<name>/manifests/<reference>", methods=['PUT'])
def put_manifest(name, reference):
    if request.content_type != 'application/vnd.oci.image.manifest.v1+json':
        return '', 400

    manifest = request.get_json()
    if manifest is None:
        return '', 400

    save_blob_to_file('manifests', f'{name}_{reference}', request.data)

    return '', 201, {'Location': f'/v2/{name}/manifests/{reference}'}


# end-8ab
@app.route('/v2/<name>/tags/list', methods=['GET'])
def get_tags_list(name):
    last_tag = request.args.get('last')
    amount = request.args.get('n')
    if not amount or not last_tag:
        # end-8b
        return '', 200

    # end-8a
    return '', 200


# end-9
@app.route('/v2/<name>/manifests/<reference>', methods=['DELETE'])
def delete_manifest_by_reference(name, reference):
    file_path = os.path.join('manifests', f'{name}_{reference}')
    if os.path.exists(file_path):
        os.remove(file_path)
        return '', 202
    return '', 404


# end-10
@app.route('/v2/<name>/blobs/<digest>', methods=['DELETE'])
def delete_blob_by_digest(name, digest):
    file_path = os.path.join('blobs', f'{name}_{digest}')
    if os.path.exists(file_path):
        os.remove(file_path)
        return '', 202
    return '', 404


# end-12ab
@app.route('/v2/<name>/referrers/<digest>', methods=['GET'])
def get_referrers(name, digest):
    artifact_type = request.args.get('artifactType')
    if artifact_type:
        # end-12b
        return '', 200

    # end-12a
    return '', 200


# end-13
@app.route('/v2/<name>/blobs/uploads/<location>', methods=['GET'])
def get_blob_upload_status(name, location):
    file_path = os.path.join('blobs', location)
    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
        return '', 204, {'Location': location, 'Range': f'0-{file_size-1}'}
    return '', 404


def save_blob_to_file(directory, filename, data):
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(os.path.join(directory, filename), 'wb') as file:
        file.write(data)


def find_blob_file(directory, filename):
    file_path = os.path.join(directory, filename)
    if os.path.exists(file_path):
        with open(file_path, 'rb') as file:
            return file.read()
    return None


# https://github.com/opencontainers/distribution-spec/blob/main/spec.md
if __name__ == '__main__':
    app.run(debug=True)
