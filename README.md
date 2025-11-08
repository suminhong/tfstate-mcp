# Terraform tfstate 분석 MCP 서버

AWS S3에 저장된 Terraform tfstate 파일을 읽고 분석하는 MCP(Model Context Protocol) 서버입니다.

## 기능

이 MCP 서버는 다음 두 가지 도구를 제공합니다:

1. **list_tfstate_files**: S3 버킷에 존재하는 모든 `.tfstate` 파일의 경로 리스트를 반환
2. **read_tfstate**: 특정 tfstate 파일을 읽고 리소스 정보를 검색

## 설치

```bash
pip install -r requirements.txt
```

## AWS 자격증명 설정

다음 두 가지 방법 중 하나를 선택하여 AWS 자격증명을 설정할 수 있습니다:

### 방법 1: AWS 프로필 사용 (권장)

AWS CLI로 프로필을 설정한 후, 도구 호출 시 `profile_name` 파라미터로 프로필 이름을 전달합니다.

```bash
# AWS 프로필 설정
aws configure --profile myprofile
```

### 방법 2: 환경변수 사용

환경변수로 AWS 자격증명을 설정합니다:

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

## 실행

```bash
python main.py
```

기본적으로 stdio 전송 프로토콜을 사용합니다. 다른 프로토콜을 사용하려면:

```bash
python main.py --transport sse
```

## 도구 사용법

### 1. list_tfstate_files

S3 버킷의 모든 tfstate 파일 경로를 나열합니다.

**파라미터:**
- `bucket_name` (필수): S3 버킷 이름
- `prefix` (선택): 검색할 접두사 (예: 'terraform/prod/')
- `profile_name` (선택): AWS 프로필 이름

**예시 응답:**
```json
{
  "bucket": "my-terraform-bucket",
  "prefix": "terraform/",
  "total_files": 3,
  "tfstate_files": [
    "terraform/prod/terraform.tfstate",
    "terraform/dev/terraform.tfstate",
    "terraform/staging/terraform.tfstate"
  ]
}
```

### 2. read_tfstate

특정 tfstate 파일을 읽고 리소스 정보를 반환합니다.

**파라미터:**
- `bucket_name` (필수): S3 버킷 이름
- `tfstate_path` (필수): tfstate 파일의 S3 경로
- `search_query` (선택): 검색할 리소스 타입 또는 이름 (예: 'aws_instance', 'my-server')
- `profile_name` (선택): AWS 프로필 이름

**예시 응답:**
```json
{
  "version": 4,
  "terraform_version": "1.5.0",
  "serial": 42,
  "lineage": "abc123-def456",
  "total_resources": 5,
  "resources": [
    {
      "type": "aws_instance",
      "name": "web_server",
      "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
      "mode": "managed",
      "instances": [
        {
          "attributes": {
            "id": "i-1234567890abcdef0",
            "instance_type": "t2.micro",
            "ami": "ami-0c55b159cbfafe1f0"
          },
          "status": "tainted",
          "schema_version": 1
        }
      ]
    }
  ]
}
```

## MCP 클라이언트 설정

Claude Desktop 또는 다른 MCP 클라이언트에서 이 서버를 사용하려면, 설정 파일에 다음과 같이 추가하세요:

```json
{
  "mcpServers": {
    "tfstate-analyzer": {
      "command": "python",
      "args": ["/path/to/tfstate-mcp/main.py"],
      "env": {
        "AWS_ACCESS_KEY_ID": "your_access_key",
        "AWS_SECRET_ACCESS_KEY": "your_secret_key"
      }
    }
  }
}
```

프로필을 사용하는 경우 `env` 섹션은 생략할 수 있습니다.

## 에러 처리

서버는 다음과 같은 에러 상황을 처리합니다:

- **NoSuchBucket**: 지정된 버킷을 찾을 수 없음
- **AccessDenied**: 버킷 또는 파일에 대한 접근 권한 없음
- **NoSuchKey**: 지정된 파일을 찾을 수 없음
- **NoCredentialsError**: AWS 자격증명을 찾을 수 없음
- **JSONDecodeError**: tfstate 파일이 유효한 JSON 형식이 아님

## 라이센스

MIT License

## 기여

이슈 및 풀 리퀘스트를 환영합니다!
