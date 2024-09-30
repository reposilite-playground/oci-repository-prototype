import json
import os
import unittest

from app import app


class TestFlaskEndpoints(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Ensure directories exist for blobs and manifests
        os.makedirs('blobs', exist_ok=True)
        os.makedirs('manifests', exist_ok=True)

    def tearDown(self):
        # Cleanup the blobs directory after each test
        for filename in os.listdir('blobs'):
            os.remove(os.path.join('blobs', filename))

        # Cleanup the manifests directory after each test
        for filename in os.listdir('manifests'):
            os.remove(os.path.join('manifests', filename))

    # Test for /v2
    def test_verify_specification_implementation(self):
        response = self.app.get('/v2')
        self.assertEqual(response.status_code, 200)

    # Tests for /v2/<name>/blobs/uploads/
    def test_upload_blob_success(self):
        name = "test_name"
        digest = "test_digest"
        data = b"test binary data"
        response = self.app.post(
            f'/v2/{name}/blobs/uploads/?digest={digest}',
            data=data,
            content_type='application/octet-stream'
        )
        self.assertEqual(response.status_code, 202)

    def test_upload_blob_missing_digest(self):
        response = self.app.post('/v2/test_name/blobs/uploads/', data=b"test")
        self.assertEqual(response.status_code, 400)

    def test_upload_blob_invalid_content_type(self):
        response = self.app.post('/v2/test_name/blobs/uploads/?digest=test_digest',
                                 data=b"test",
                                 content_type='text/plain')
        self.assertEqual(response.status_code, 400)

    # Tests for /v2/<name>/blobs/<digest>
    def test_get_blob_success(self):
        with open('blobs/test_name_test_digest', 'wb') as f:
            f.write(b'Test data for blob retrieval.')

        response = self.app.get('/v2/test_name/blobs/test_digest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'Test data for blob retrieval.')

    def test_get_blob_not_found(self):
        response = self.app.get('/v2/test_name/blobs/unknown_digest')
        self.assertEqual(response.status_code, 404)

    def test_delete_blob_success(self):
        with open('blobs/test_name_test_digest', 'wb') as f:
            f.write(b'Test data for deletion.')

        response = self.app.delete('/v2/test_name/blobs/test_digest')
        self.assertEqual(response.status_code, 202)

    def test_delete_blob_not_found(self):
        response = self.app.delete('/v2/test_name/blobs/unknown_digest')
        self.assertEqual(response.status_code, 404)

    # Tests for manifest endpoints
    def test_put_manifest_success(self):
        name = "test_name"
        reference = "test_reference"
        manifest_data = json.dumps({"key": "value"})
        response = self.app.put(
            f'/v2/{name}/manifests/{reference}',
            data=manifest_data,
            content_type='application/vnd.oci.image.manifest.v1+json'
        )
        self.assertEqual(response.status_code, 201)

    def test_put_manifest_invalid_content_type(self):
        response = self.app.put('/v2/test_name/manifests/test_reference',
                                data=b'test',
                                content_type='text/plain')
        self.assertEqual(response.status_code, 400)

    def test_get_manifest_success(self):
        name = "test_name"
        reference = "test_reference"
        with open('manifests/test_name_test_reference', 'wb') as f:
            f.write(b'Test manifest data.')

        response = self.app.get(f'/v2/{name}/manifests/{reference}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'Test manifest data.')

    def test_get_manifest_not_found(self):
        response = self.app.get('/v2/test_name/manifests/unknown_reference')
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
