import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import get_backend
import main

class TestAuthLogic(unittest.TestCase):
    def setUp(self):
        main.backend = None
        self.env_patcher = patch.dict(os.environ, {"TFSTATE_BUCKET_NAME": "test-bucket"}, clear=True)
        self.env_patcher.start()
        
        self.mock_boto3_patcher = patch('backends.s3.boto3')
        self.mock_boto3 = self.mock_boto3_patcher.start()
        self.mock_session = MagicMock()
        self.mock_boto3.Session.return_value = self.mock_session

    def tearDown(self):
        self.env_patcher.stop()
        self.mock_boto3_patcher.stop()

    def test_default_profile_fallback(self):
        # No AWS env vars set (cleared in setUp)
        get_backend()
        # Should call Session(profile_name='default')
        self.mock_boto3.Session.assert_called_with(profile_name='default')

    def test_aws_profile_env(self):
        with patch.dict(os.environ, {"AWS_PROFILE": "custom-profile"}):
            get_backend()
            self.mock_boto3.Session.assert_called_with(profile_name='custom-profile')

    def test_aws_access_key_env(self):
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "key", "AWS_SECRET_ACCESS_KEY": "secret"}):
            get_backend()
            # Should NOT pass profile_name='default'
            # S3Backend logic will see keys and pass them to Session
            # But here we check what get_backend passed to S3Backend constructor
            # Wait, get_backend calls S3Backend(..., profile_name=None)
            # S3Backend then calls boto3.Session(aws_access_key_id=...)
            
            # Let's verify S3Backend init call args indirectly via boto3.Session call
            # If profile_name was passed as None to S3Backend, it won't be in session_kwargs (unless keys are there)
            
            # In this case, get_backend passes profile_name=None
            # S3Backend sees keys in env (via os.environ, wait S3Backend doesn't read env for keys anymore? 
            # Ah, S3Backend constructor takes keys as args, but get_backend ONLY passes profile_name.
            # S3Backend implementation:
            # if aws_access_key_id and aws_secret_access_key: ...
            # else: session = boto3.Session(**session_kwargs)
            
            # Wait, S3Backend.__init__ uses arguments.
            # get_backend ONLY passes bucket_name and profile_name.
            # So S3Backend will see None for keys.
            # Then S3Backend._get_s3_client:
            # if profile_name: ...
            # if aws_access_key_id ...
            # session = boto3.Session(**session_kwargs)
            
            # If keys are in ENV, boto3.Session() picks them up automatically if no conflicting args.
            # So if profile_name is None, session_kwargs is empty.
            # boto3.Session() is called with empty args.
            # It should pick up env vars.
            
            self.mock_boto3.Session.assert_called_with()

if __name__ == '__main__':
    unittest.main()
