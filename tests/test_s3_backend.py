import unittest
from unittest.mock import MagicMock, patch
import json
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backends.s3 import S3Backend

class TestS3Backend(unittest.TestCase):
    def setUp(self):
        self.bucket_name = "test-bucket"
        self.mock_boto3_patcher = patch('backends.s3.boto3')
        self.mock_boto3 = self.mock_boto3_patcher.start()
        self.mock_session = MagicMock()
        self.mock_client = MagicMock()
        self.mock_boto3.Session.return_value = self.mock_session
        self.mock_session.client.return_value = self.mock_client
        
    def tearDown(self):
        self.mock_boto3_patcher.stop()

    def test_init_with_profile(self):
        S3Backend(bucket_name=self.bucket_name, profile_name="test-profile")
        self.mock_boto3.Session.assert_called_with(profile_name="test-profile")

    def test_init_with_keys(self):
        S3Backend(
            bucket_name=self.bucket_name,
            aws_access_key_id="key",
            aws_secret_access_key="secret"
        )
        self.mock_boto3.Session.assert_called_with(
            aws_access_key_id="key",
            aws_secret_access_key="secret"
        )

    def test_list_states(self):
        backend = S3Backend(bucket_name=self.bucket_name)
        
        # Mock paginator
        paginator = MagicMock()
        self.mock_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                'Contents': [
                    {'Key': 'state1.tfstate'},
                    {'Key': 'other.txt'},
                    {'Key': 'path/state2.tfstate'}
                ]
            }
        ]
        
        states = backend.list_states()
        self.assertEqual(states, ['state1.tfstate', 'path/state2.tfstate'])
        self.mock_client.get_paginator.assert_called_with('list_objects_v2')

    def test_get_state(self):
        backend = S3Backend(bucket_name=self.bucket_name)
        
        mock_state = {
            "version": 4,
            "resources": []
        }
        
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(mock_state).encode('utf-8')
        self.mock_client.get_object.return_value = {'Body': mock_body}
        
        state = backend.get_state("test.tfstate")
        self.assertEqual(state, mock_state)
        self.mock_client.get_object.assert_called_with(Bucket=self.bucket_name, Key="test.tfstate")

if __name__ == '__main__':
    unittest.main()
