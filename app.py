import os

from flask import Flask, request

app = Flask(__name__)


@app.route('/v2', methods=['GET'])
def verify_specification_implementation():
    return '', 200


def save_blob_to_file(directory, filename, data):
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(os.path.join(directory, filename), 'wb') as file:
        file.write(data)


@app.route('/v2/<name>/blobs/uploads/', methods=['POST'])
def upload_blob(name):
    digest = request.args.get('digest')
    if not digest:
        return '', 400

    if request.content_length is None or request.content_type != 'application/octet-stream':
        return '', 400

    binary_blob = request.data

    save_blob_to_file('blobs', f'{name}_{digest}', binary_blob)

    return '', 202, {'Location': f'/v2/{name}/blobs/{digest}'}


def find_blob_file(directory, filename):
    file_path = os.path.join(directory, filename)
    if os.path.exists(file_path):
        with open(file_path, 'rb') as file:
            return file.read()
    return None


@app.route('/v2/<name>/blobs/<digest>', methods=['DELETE'])
def delete_blob_by_digest(name, digest):
    file_path = os.path.join('blobs', f'{name}_{digest}')
    if os.path.exists(file_path):
        os.remove(file_path)
        return '', 202
    return '', 404


@app.route('/v2/<name>/blobs/<digest>', methods=['GET', 'HEAD'])
def get_blob_by_digest(name, digest):
    file_content = find_blob_file('blobs', f'{name}_{digest}')
    if file_content is None:
        return '', 404
    return file_content, 200, {'Docker-Content-Digest': digest}


@app.route("/v2/<name>/manifests/<reference>", methods=['PUT'])
def put_manifest(name, reference):
    if request.content_type != 'application/vnd.oci.image.manifest.v1+json':
        return '', 400

    manifest = request.get_json()
    if manifest is None:
        return '', 400

    save_blob_to_file('manifests', f'{name}_{reference}', request.data)

    return '', 201, {'Location': f'/v2/{name}/manifests/{reference}'}


@app.route('/v2/<name>/manifests/<reference>', methods=['GET', 'HEAD'])
def get_manifest_by_reference(name, reference):
    file_content = find_blob_file('manifests', f'{name}_{reference}')
    if file_content is None:
        return '', 404

    return file_content, 200, {'Docker-Content-Digest': reference}


if __name__ == '__main__':
    app.run(debug=True)
