# Sentra Collector 설치

모니터링 대상 Linux 서버에 Sentra Collector를 설치하는 공개 배포 저장소입니다.
전체 Sentra 소스 없이 GHCR 이미지를 받아 실행합니다. 이미지 주소:
`ghcr.io/seyun24/sentra-collector:v0.1.0` (관리자가 최초 publish 및 Public 설정 필요).

## 준비

- Native Linux (Ubuntu 24.04 권장), x86_64. 최초 이미지는 linux/amd64 전용입니다.
- Docker Engine, Docker Compose **2.30.0 이상**, Python 3, Git.
- Docker 설치: https://docs.docker.com/engine/install/ubuntu/
- 대상 서버에서 Sentra의 공개 HTTPS Ingest 주소로 나가는 연결 허용.
- Sentra 수집기 등록 화면에서 발급한 workspace/Collector/host ID와 전용 토큰.

## 설치

```bash
git clone https://github.com/seyun24/sentra-collector.git
cd sentra-collector
cp collector.env.example collector.env
# collector.env를 편집해 Sentra에서 발급받은 실제 설정 입력
chmod 600 collector.env
sudo bash install.sh check
sudo bash install.sh
```

설정 파일은 `KEY=value` 원문 형식입니다. 값에 따옴표를 추가하지 마세요.
`$`, `#` 등은 raw env_file 처리로 보존됩니다. 셸로 source하지 않습니다.
실제 토큰과 DB 비밀번호가 담긴 collector.env는 Git에 올리지 마세요.

설치 후 Sentra에서 같은 workspace를 선택하고 heartbeat와 메트릭 수신을 확인하세요.
CPU·네트워크 사용률은 첫 샘플 이후 다음 주기부터 생성됩니다.
현재 Collector는 전송 실패를 메모리 큐에 보관하므로 컨테이너 실행 성공만으로
Ingest 인증·전송 성공을 판단하면 안 됩니다. 실패 중 재시작하면 메모리 큐는 사라집니다.

## 수집 범위

- CPU·메모리·load: Linux /proc 기반.
- 프로세스: host PID namespace, 네트워크: host network namespace 사용.
- 파일시스템 지표는 이미지의 host 경로 지원이 포함된 버전을 사용합니다.
- 로그: 기본 /var/log 읽기 전용 연결. 지정한 파일만 읽습니다.
- Trace: 애플리케이션이 생성한 JSONL 파일을 읽습니다. 자동 APM 주입은 아닙니다.
- DB: SQLite 파일 또는 MySQL 연결 상태 probe. PostgreSQL probe는 현재 지원하지 않습니다.
- 복구 명령 실행은 이 배포에서 비활성화합니다. Docker socket과 privileged는 사용하지 않습니다.
- /host에 호스트 루트를 읽기 전용 연결하므로 컨테이너는 호스트 파일을 읽을 수 있습니다.
  이것이 필요하지 않으면 /host mount를 제거하세요. 해당 버전의 디스크 지표도 함께 확인하세요.
- OS inventory의 배포판 표시는 컨테이너 이미지 기준일 수 있습니다.
- 대상 서버의 inbound 포트는 열 필요 없습니다. 현재 Collector에는 상태 HTTP 서버가 없습니다.

## 별도 로그·Trace·SQLite 경로

`compose.override.yml`을 만들면 설치 스크립트가 함께 적용합니다.
경로가 실제로 존재해야 합니다. 필요한 디렉터리만 읽기 전용으로 연결하세요.

```yaml
services:
  collector:
    volumes:
      - type: bind
        source: /opt/myapp/logs
        target: /opt/myapp/logs
        read_only: true
        bind:
          create_host_path: false
```

collector.env의 파일 경로도 컨테이너 안에서 보이는 동일 경로로 설정합니다.
SQLite WAL 모드 파일은 해당 디렉터리와 -wal/-shm 파일도 읽을 수 있어야 합니다.

## 운영

```bash
sudo bash install.sh status
sudo bash install.sh logs
sudo bash install.sh stop
sudo bash install.sh update
sudo bash install.sh uninstall
```

uninstall은 컨테이너·네트워크만 제거하고 설정 파일과 읽기 위치 state 볼륨을 유지합니다.
Docker가 부팅 때 시작되어야 unless-stopped 정책으로 자동 재실행됩니다.

업데이트는 버전을 지정해 실행합니다:

```bash
sudo env COLLECTOR_IMAGE=ghcr.io/seyun24/sentra-collector:v0.1.1 bash install.sh update
```

이 override는 해당 명령에서만 유효합니다. 기본 버전을 영구 변경하려면 compose.yml의
기본 이미지 태그를 수정합니다. 이전 태그를 지정하면 이전 이미지로 돌아갈 수 있습니다.

## 관리자: 이미지 빌드·게시

비공개 Sentra 소스 저장소에서 실행합니다. 이 공개 설치 저장소에는 전체 소스를 복사하지 않습니다.

```bash
# 최초 빌드 전 비공개 소스 저장소 루트에서 host 디스크 지원 패치 적용
# 이미 적용했다면 생략
git apply /path/to/sentra-collector/patches/host-disk-root.patch
# Docker build context는 Sentra 저장소 루트

docker build --platform linux/amd64 -f collector/Dockerfile \
  -t ghcr.io/seyun24/sentra-collector:v0.1.0 .
# GitHub PAT classic의 write:packages 권한으로 ghcr.io 로그인 (stdin 사용)
docker push ghcr.io/seyun24/sentra-collector:v0.1.0
```

GitHub 계정 → Packages → sentra-collector → Package settings에서 Public으로 변경합니다.
설치 파일의 공개와 이미지의 공개 설정은 별개입니다. 이미지에 비밀값이 없는지 확인한
후 공개하세요. Python 코드가 들어 있는 이미지는 다운로드한 사람이 코드를 볼 수 있습니다.
소스 저장소가 비공개여도 이미지에 포함된 Collector 코드는 비공개가 아닙니다.
