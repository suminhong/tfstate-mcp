import json
import os
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .base import StateBackend

class S3Backend(StateBackend):
    """S3 backend implementation for Terraform state"""
    
    def __init__(
        self,
        bucket_name: str,
        profile_name: Optional[str] = None,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None
    ):
        """
        Initialize S3 backend
        
        Args:
            bucket_name: S3 bucket name
            profile_name: AWS profile name
            region_name: AWS region name
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
            aws_session_token: AWS session token
        """
        self.bucket_name = bucket_name
        self.client = self._get_s3_client(
            profile_name,
            region_name,
            aws_access_key_id,
            aws_secret_access_key,
            aws_session_token
        )

    def _get_s3_client(
        self,
        profile_name: Optional[str] = None,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None
    ) -> boto3.client:
        """Create boto3 S3 client with provided credentials"""
        try:
            session_kwargs = {}
            if profile_name:
                session_kwargs['profile_name'] = profile_name
            if region_name:
                session_kwargs['region_name'] = region_name
                
            # If explicit credentials are provided, they override profile/env
            if aws_access_key_id and aws_secret_access_key:
                session_kwargs['aws_access_key_id'] = aws_access_key_id
                session_kwargs['aws_secret_access_key'] = aws_secret_access_key
                if aws_session_token:
                    session_kwargs['aws_session_token'] = aws_session_token
            
            session = boto3.Session(**session_kwargs)
            return session.client('s3')
            
        except NoCredentialsError:
            raise ValueError(
                "AWS credentials not found. "
                "Please provide profile_name, set environment variables, "
                "or provide access keys explicitly."
            )
        except Exception as e:
            raise ValueError(f"Failed to create S3 client: {str(e)}")

    def list_states(self, prefix: str = "") -> list[str]:
        """List all .tfstate files in the bucket"""
        tfstate_files = []
        
        try:
            paginator = self.client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        if key.endswith('.tfstate'):
                            tfstate_files.append(key)
            
            return tfstate_files
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                raise ValueError(f"Bucket '{self.bucket_name}' not found.")
            elif error_code == 'AccessDenied':
                raise ValueError(f"Access denied to bucket '{self.bucket_name}'.")
            else:
                raise ValueError(f"S3 Error: {str(e)}")

    def get_state(self, path: str) -> dict[str, Any]:
        """Read and parse tfstate file from S3"""
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=path)
            tfstate_content = response['Body'].read().decode('utf-8')
            return json.loads(tfstate_content)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise ValueError(f"File '{path}' not found in bucket '{self.bucket_name}'.")
            elif error_code == 'AccessDenied':
                raise ValueError(f"Access denied to file '{path}'.")
            else:
                raise ValueError(f"S3 Error: {str(e)}")
        except json.JSONDecodeError:
            raise ValueError(f"File '{path}' is not valid JSON.")
