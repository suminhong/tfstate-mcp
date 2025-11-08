import argparse
import json
import os
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from mcp.server import Server
from mcp.types import Tool, TextContent

# MCP 서버 초기화
mcp = Server("tfstate-analyzer")

# AWS S3 클라이언트를 저장할 전역 변수
s3_client = None


def get_s3_client(profile_name: Optional[str] = None) -> boto3.client:
    """
    AWS S3 클라이언트를 생성합니다.
    
    Args:
        profile_name: AWS 프로필 이름 (선택사항)
    
    Returns:
        boto3 S3 클라이언트
    """
    global s3_client
    
    if s3_client is not None:
        return s3_client
    
    try:
        if profile_name:
            # 프로필 이름이 제공된 경우
            session = boto3.Session(profile_name=profile_name)
            s3_client = session.client('s3')
        else:
            # 환경변수 또는 기본 자격증명 사용
            aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
            aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
            
            if aws_access_key and aws_secret_key:
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key
                )
            else:
                # 기본 자격증명 체인 사용
                s3_client = boto3.client('s3')
        
        return s3_client
    
    except NoCredentialsError:
        raise ValueError(
            "AWS 자격증명을 찾을 수 없습니다. "
            "프로필 이름을 제공하거나 AWS_ACCESS_KEY_ID와 AWS_SECRET_ACCESS_KEY 환경변수를 설정하세요."
        )
    except Exception as e:
        raise ValueError(f"S3 클라이언트 생성 실패: {str(e)}")


def list_tfstate_files(bucket_name: str, prefix: str = "", profile_name: Optional[str] = None) -> list[str]:
    """
    S3 버킷에서 모든 .tfstate 파일 경로를 반환합니다.
    
    Args:
        bucket_name: S3 버킷 이름
        prefix: 검색할 접두사 (선택사항)
        profile_name: AWS 프로필 이름 (선택사항)
    
    Returns:
        .tfstate 파일 경로 리스트
    """
    client = get_s3_client(profile_name)
    tfstate_files = []
    
    try:
        paginator = client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        
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
            raise ValueError(f"버킷 '{bucket_name}'을 찾을 수 없습니다.")
        elif error_code == 'AccessDenied':
            raise ValueError(f"버킷 '{bucket_name}'에 대한 접근 권한이 없습니다.")
        else:
            raise ValueError(f"S3 오류: {str(e)}")


def read_and_search_tfstate(
    bucket_name: str,
    tfstate_path: str,
    search_query: Optional[str] = None,
    profile_name: Optional[str] = None
) -> dict[str, Any]:
    """
    S3에서 tfstate 파일을 읽고 리소스 정보를 검색합니다.
    
    Args:
        bucket_name: S3 버킷 이름
        tfstate_path: tfstate 파일 경로
        search_query: 검색할 리소스 타입 또는 이름 (선택사항)
        profile_name: AWS 프로필 이름 (선택사항)
    
    Returns:
        tfstate 파일 정보 및 리소스 리스트
    """
    client = get_s3_client(profile_name)
    
    try:
        # S3에서 tfstate 파일 읽기
        response = client.get_object(Bucket=bucket_name, Key=tfstate_path)
        tfstate_content = response['Body'].read().decode('utf-8')
        tfstate_data = json.loads(tfstate_content)
        
        # 기본 정보 추출
        result = {
            "version": tfstate_data.get("version"),
            "terraform_version": tfstate_data.get("terraform_version"),
            "serial": tfstate_data.get("serial"),
            "lineage": tfstate_data.get("lineage"),
            "resources": []
        }
        
        # 리소스 정보 추출
        resources = tfstate_data.get("resources", [])
        
        for resource in resources:
            resource_info = {
                "type": resource.get("type"),
                "name": resource.get("name"),
                "provider": resource.get("provider"),
                "mode": resource.get("mode"),
                "instances": []
            }
            
            # 인스턴스 정보 추출
            instances = resource.get("instances", [])
            for instance in instances:
                instance_info = {
                    "attributes": instance.get("attributes", {}),
                    "status": instance.get("status"),
                    "schema_version": instance.get("schema_version")
                }
                resource_info["instances"].append(instance_info)
            
            # 검색 쿼리가 있는 경우 필터링
            if search_query:
                if (search_query.lower() in resource_info["type"].lower() or
                    search_query.lower() in resource_info["name"].lower()):
                    result["resources"].append(resource_info)
            else:
                result["resources"].append(resource_info)
        
        result["total_resources"] = len(result["resources"])
        
        return result
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            raise ValueError(f"파일 '{tfstate_path}'을 버킷 '{bucket_name}'에서 찾을 수 없습니다.")
        elif error_code == 'AccessDenied':
            raise ValueError(f"파일 '{tfstate_path}'에 대한 접근 권한이 없습니다.")
        else:
            raise ValueError(f"S3 오류: {str(e)}")
    except json.JSONDecodeError:
        raise ValueError(f"파일 '{tfstate_path}'은 유효한 JSON 형식이 아닙니다.")


@mcp.list_tools()
async def list_tools() -> list[Tool]:
    """사용 가능한 도구 목록을 반환합니다."""
    return [
        Tool(
            name="list_tfstate_files",
            description=(
                "S3 버킷에 존재하는 모든 .tfstate 파일의 경로 리스트를 반환합니다. "
                "AWS 자격증명은 profile_name 파라미터로 프로필을 지정하거나, "
                "환경변수 AWS_ACCESS_KEY_ID와 AWS_SECRET_ACCESS_KEY를 사용합니다."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket_name": {
                        "type": "string",
                        "description": "S3 버킷 이름"
                    },
                    "prefix": {
                        "type": "string",
                        "description": "검색할 접두사 (선택사항, 예: 'terraform/prod/')",
                        "default": ""
                    },
                    "profile_name": {
                        "type": "string",
                        "description": "AWS 프로필 이름 (선택사항)"
                    }
                },
                "required": ["bucket_name"]
            }
        ),
        Tool(
            name="read_tfstate",
            description=(
                "S3에서 특정 tfstate 파일을 읽고 리소스 정보를 반환합니다. "
                "선택적으로 search_query를 제공하여 특정 리소스 타입이나 이름으로 필터링할 수 있습니다. "
                "AWS 자격증명은 profile_name 파라미터로 프로필을 지정하거나, "
                "환경변수 AWS_ACCESS_KEY_ID와 AWS_SECRET_ACCESS_KEY를 사용합니다."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket_name": {
                        "type": "string",
                        "description": "S3 버킷 이름"
                    },
                    "tfstate_path": {
                        "type": "string",
                        "description": "tfstate 파일의 S3 경로 (예: 'terraform/prod/terraform.tfstate')"
                    },
                    "search_query": {
                        "type": "string",
                        "description": "검색할 리소스 타입 또는 이름 (선택사항, 예: 'aws_instance', 'my-server')"
                    },
                    "profile_name": {
                        "type": "string",
                        "description": "AWS 프로필 이름 (선택사항)"
                    }
                },
                "required": ["bucket_name", "tfstate_path"]
            }
        )
    ]


@mcp.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """도구 호출을 처리합니다."""
    try:
        if name == "list_tfstate_files":
            bucket_name = arguments.get("bucket_name")
            prefix = arguments.get("prefix", "")
            profile_name = arguments.get("profile_name")
            
            files = list_tfstate_files(bucket_name, prefix, profile_name)
            
            result = {
                "bucket": bucket_name,
                "prefix": prefix,
                "total_files": len(files),
                "tfstate_files": files
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, ensure_ascii=False)
            )]
        
        elif name == "read_tfstate":
            bucket_name = arguments.get("bucket_name")
            tfstate_path = arguments.get("tfstate_path")
            search_query = arguments.get("search_query")
            profile_name = arguments.get("profile_name")
            
            result = read_and_search_tfstate(
                bucket_name,
                tfstate_path,
                search_query,
                profile_name
            )
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, ensure_ascii=False)
            )]
        
        else:
            raise ValueError(f"알 수 없는 도구: {name}")
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"오류 발생: {str(e)}"
        )]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Terraform tfstate 분석 MCP 서버")
    parser.add_argument(
        "--transport",
        type=str,
        default="stdio",
        choices=["streamable-http", "sse", "stdio"],
        help="전송 프로토콜 (기본값: stdio)",
    )
    args = parser.parse_args()

    mcp.run(transport=args.transport)
