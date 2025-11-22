import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
from main import get_backend

class TestCLIArgs(unittest.TestCase):
    def setUp(self):
        main.backend = None
        main.global_bucket_name = None
        
        self.mock_boto3_patcher = patch('backends.s3.boto3')
        self.mock_boto3 = self.mock_boto3_patcher.start()
        self.mock_session = MagicMock()
        self.mock_boto3.Session.return_value = self.mock_session

    def tearDown(self):
        self.mock_boto3_patcher.stop()

    def test_cli_override_env(self):
        # Set env var
        with patch.dict(os.environ, {"TFSTATE_BUCKET_NAME": "env-bucket"}):
            # Set global bucket name (simulating CLI arg parsing)
            main.global_bucket_name = "cli-bucket"
            
            backend = get_backend()
            self.assertEqual(backend.bucket_name, "cli-bucket")

    def test_env_fallback(self):
        # Set env var
        with patch.dict(os.environ, {"TFSTATE_BUCKET_NAME": "env-bucket"}):
            # No CLI arg
            main.global_bucket_name = None
            
            backend = get_backend()
            self.assertEqual(backend.bucket_name, "env-bucket")

if __name__ == '__main__':
    unittest.main()
