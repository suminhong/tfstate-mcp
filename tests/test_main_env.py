import unittest
from unittest.mock import MagicMock, patch
import json
import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import call_tool, get_backend
import main

class TestMainEnv(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Reset global backend
        main.backend = None
        self.env_patcher = patch.dict(os.environ, {"TFSTATE_BUCKET_NAME": "env-bucket"})
        self.env_patcher.start()
        
        self.mock_boto3_patcher = patch('backends.s3.boto3')
        self.mock_boto3 = self.mock_boto3_patcher.start()
        self.mock_session = MagicMock()
        self.mock_client = MagicMock()
        self.mock_boto3.Session.return_value = self.mock_session
        self.mock_session.client.return_value = self.mock_client
        
    def tearDown(self):
        self.env_patcher.stop()
        self.mock_boto3_patcher.stop()

    async def test_list_tools_call(self):
        # Mock S3 response
        paginator = MagicMock()
        self.mock_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                'Contents': [
                    {'Key': 'env-state.tfstate'}
                ]
            }
        ]
        
        result = await call_tool("list_tfstate_files", {"prefix": ""})
        data = json.loads(result[0].text)
        
        self.assertEqual(data["bucket"], "env-bucket")
        self.assertEqual(data["tfstate_files"], ["env-state.tfstate"])

    async def test_read_tfstate_call(self):
        # Mock S3 response
        mock_state = {
            "version": 4,
            "resources": []
        }
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(mock_state).encode('utf-8')
        self.mock_client.get_object.return_value = {'Body': mock_body}
        
        result = await call_tool("read_tfstate", {"tfstate_path": "path/to/state"})
        data = json.loads(result[0].text)
        
        self.assertEqual(data["version"], 4)
        self.mock_client.get_object.assert_called_with(Bucket="env-bucket", Key="path/to/state")

    async def test_missing_env_var(self):
        main.backend = None
        with patch.dict(os.environ, {}, clear=True):
            result = await call_tool("list_tfstate_files", {})
            self.assertIn("TFSTATE_BUCKET_NAME environment variable is not set", result[0].text)

if __name__ == '__main__':
    unittest.main()
