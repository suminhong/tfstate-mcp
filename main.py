import argparse
import json
import os
import sys
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from backends.s3 import S3Backend

# MCP 서버 초기화
# mcp-proxy가 /mcp 경로로 SSE 연결을 시도하므로 sse_path를 /mcp로 설정합니다.
mcp = FastMCP("tfstate-analyzer", sse_path="/mcp")

# 전역 백엔드 인스턴스
backend = None

# 전역 설정
global_bucket_name = None

def get_backend() -> S3Backend:
    """
    전역 백엔드 인스턴스를 반환합니다.
    없으면 환경변수 또는 전역 설정을 사용하여 초기화합니다.
    """
    global backend, global_bucket_name
    if backend is None:
        # 1. CLI 인자로 전달된 버킷 이름 확인
        bucket_name = global_bucket_name
        
        # 2. 없으면 환경변수 확인
        if not bucket_name:
            bucket_name = os.environ.get("TFSTATE_BUCKET_NAME")
            
        if not bucket_name:
            raise ValueError("TFSTATE_BUCKET_NAME environment variable is not set and no --bucket argument provided.")
        
        # AWS 자격증명 처리 로직
        profile_name = os.environ.get("AWS_PROFILE")
        aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        
        if not profile_name and not aws_access_key:
            profile_name = "default"
            
        backend = S3Backend(bucket_name=bucket_name, profile_name=profile_name)
    
    return backend

@mcp.tool()
def list_tfstate_files(prefix: str = "") -> str:
    """
    S3 버킷에 존재하는 모든 .tfstate 파일의 경로 리스트를 반환합니다.
    버킷과 자격증명은 서버 환경변수를 통해 사전 설정되어 있습니다.
    
    Args:
        prefix: 검색할 접두사 (선택사항, 예: 'terraform/prod/')
    """
    try:
        s3_backend = get_backend()
        files = s3_backend.list_states(prefix)
        
        result = {
            "bucket": s3_backend.bucket_name,
            "prefix": prefix,
            "total_files": len(files),
            "tfstate_files": files
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def read_tfstate(tfstate_path: str, search_query: Optional[str] = None) -> str:
    """
    S3에서 특정 tfstate 파일을 읽고 리소스 정보를 반환합니다.
    
    Args:
        tfstate_path: tfstate 파일의 S3 경로 (예: 'terraform/prod/terraform.tfstate')
        search_query: 검색할 리소스 타입 또는 이름 (선택사항, 예: 'aws_instance', 'my-server')
    """
    try:
        s3_backend = get_backend()
        
        # Get raw state
        tfstate_data = s3_backend.get_state(tfstate_path)
        
        # Process state data
        result = {
            "version": tfstate_data.get("version"),
            "terraform_version": tfstate_data.get("terraform_version"),
            "serial": tfstate_data.get("serial"),
            "lineage": tfstate_data.get("lineage"),
            "resources": []
        }
        
        resources = tfstate_data.get("resources", [])
        
        for resource in resources:
            resource_info = {
                "type": resource.get("type"),
                "name": resource.get("name"),
                "provider": resource.get("provider"),
                "mode": resource.get("mode"),
                "instances": []
            }
            
            instances = resource.get("instances", [])
            for instance in instances:
                instance_info = {
                    "attributes": instance.get("attributes", {}),
                    "status": instance.get("status"),
                    "schema_version": instance.get("schema_version")
                }
                resource_info["instances"].append(instance_info)
            
            if search_query:
                if (search_query.lower() in resource_info["type"].lower() or
                    search_query.lower() in resource_info["name"].lower()):
                    result["resources"].append(resource_info)
            else:
                result["resources"].append(resource_info)
        
        result["total_resources"] = len(result["resources"])
        
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Terraform tfstate 분석 MCP 서버")
    parser.add_argument(
        "--transport",
        type=str,
        default="sse",
        choices=["streamable-http", "sse", "stdio"],
        help="전송 프로토콜 (기본값: sse)",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        help="S3 버킷 이름 (환경변수 TFSTATE_BUCKET_NAME보다 우선함)",
    )
    args = parser.parse_args()

    # CLI 인자로 버킷 이름 설정
    if args.bucket:
        global_bucket_name = args.bucket
        print(f"Info: Using bucket '{args.bucket}' from CLI argument.", file=sys.stderr)
    elif os.environ.get("TFSTATE_BUCKET_NAME"):
        print(f"Info: Using bucket '{os.environ.get('TFSTATE_BUCKET_NAME')}' from environment variable.", file=sys.stderr)
    else:
        print("Warning: TFSTATE_BUCKET_NAME not set and no --bucket argument provided.", file=sys.stderr)

    # 디버그 정보 출력
    print(f"Debug: AWS_PROFILE={os.environ.get('AWS_PROFILE', 'Not Set')}", file=sys.stderr)
    print(f"Debug: AWS_ACCESS_KEY_ID={'Set' if os.environ.get('AWS_ACCESS_KEY_ID') else 'Not Set'}", file=sys.stderr)

    mcp.run(transport=args.transport)
