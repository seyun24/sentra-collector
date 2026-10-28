# Sentra Collector 설치

모니터링 대상 Linux 서버에서 설정 파일 하나와 설치 스크립트로 Collector를 실행합니다.
전체 Sentra 소스, Git clone, 대상 서버에서 이미지 빌드는 필요 없습니다.
공개 이미지: `ghcr.io/seyun24/sentra-collector:v0.1.0` (linux/amd64).
설치 도구 릴리스는 `v0.2.0`이며 Collector 이미지 버전과 별개입니다.

## 설치

필요한 것: native Linux x86_64, Docker Engine, Compose 2.30 이상, Python 3, curl.
[Ubuntu Docker 설치](https://docs.docker.com/engine/install/ubuntu/).

1. Sentra에서 수집기를 등록하고 발급받은 설정을 **collector.env**로 저장합니다.
   설정 다운로드 UI가 없는 배포에서는 `collector.env.example`을 참고해 발급값을 입력합니다.
2. 대상 서버의 별도 설치 디렉터리에 collector.env를 놓습니다.
3. 같은 디렉터리에서 아래 명령을 실행합니다.

```bash
curl -fSL https://raw.githubusercontent.com/seyun24/sentra-collector/v0.2.0/install.sh -o install.sh
chmod 600 collector.env
sudo bash install.sh check
sudo bash install.sh
```

스크립트는 같은 릴리스의 설정 도구를 내려받고, env 경로를 검증하고,
`compose.generated.json`을 생성한 뒤 GHCR 이미지를 받아 실행합니다.
실제 설정 파일과 생성 파일은 Git에 올리지 않습니다.
Docker가 서버 부팅 때 시작되면 Collector도 자동 재시작합니다.
기존 Collector를 옮겨 설치할 때는 같은 설치 디렉터리와 state 볼륨을 유지하세요.

설정 값은 `KEY=value` 원문이며 따옴표로 감싸지 않습니다. `$`, `#`는 원문으로 보존합니다.
스크립트는 env를 셸로 source하거나 eval하지 않습니다.

## 입력 경로에 따른 자동 마운트

예시:

```dotenv
SENTRA_COLLECTOR_LOG_SOURCES=/opt/myapp/logs/app.log:checkout:application
SENTRA_COLLECTOR_TRACE_JSONL_PATH=/srv/traces/spans.jsonl
SENTRA_COLLECTOR_DB_SQLITE_PATH=/srv/data/demo.sqlite
```

설치 도구가 각 파일의 상위 디렉터리를 찾아 읽기 전용으로 연결합니다.
같은 디렉터리는 한 번만 연결합니다. 호스트 경로는 컨테이너의 `/inputs/0`,
`/inputs/1` 등으로 연결하고 실제 Collector 입력 설정도 자동으로 바꿉니다.
따라서 원래 env의 호스트 경로를 직접 컨테이너용 경로로 수정하지 마세요.
표시되는 로그 source_path는 컨테이너 내부 `/inputs/...` 경로입니다.

- 파일은 아직 없어도 되지만 상위 디렉터리는 존재해야 합니다.
- 파일 교체/rotation에 대응하기 위해 단일 파일 대신 디렉터리를 연결합니다.
- 심볼릭 링크는 실제 대상 경로로 해석합니다. 설치 후 다른 경로로 링크를 바꾸면 다시 설치하세요.
- 공백과 `$`가 포함된 경로도 지원합니다.
- 로그 설정 구분자인 `,`, `:`가 들어간 파일명은 지원하지 않습니다.
- 호스트 전체 `/`는 연결하지 않으며 `/proc`, `/sys`, `/dev` 파일 입력은 거부합니다.
- MySQL은 네트워크 접속이므로 파일 마운트가 필요 없습니다.
- SQLite WAL 모드라면 동일 디렉터리의 -wal/-shm 파일도 읽을 수 있어야 합니다.
- env의 파일 경로를 바꾼 후 `sudo bash install.sh`를 다시 실행하면 마운트도 갱신됩니다.
- 기존 compose.override.yml은 자동으로 읽지 않습니다. 마운트의 기준은 collector.env입니다.

## 호스트 지표와 파일 수집은 별도

```dotenv
SENTRA_INSTALL_HOST_METRICS=true
```

기본 true는 호스트 PID와 network namespace를 사용해 프로세스와 네트워크 지표를 읽습니다.
false면 컨테이너 PID/network 격리를 유지하며 해당 지표도 컨테이너 범위입니다.
CPU/메모리는 현재 이미지의 Linux /proc 구현을 사용합니다.
Docker socket, privileged, 호스트 루트 마운트는 사용하지 않습니다.

**현재 v0.1.0 이미지의 호스트 디스크 지표는 루트 마운트가 필요해서 이 설치에서는 제외합니다.**
컨테이너 디스크를 호스트 디스크로 잘못 표시하지 않도록 디스크 측정을 비활성화합니다.
OS inventory의 배포판 표시는 컨테이너 이미지 기준일 수 있습니다.
복구 명령 실행도 비활성화합니다.

## 수신 확인과 상태 보존

Collector는 공개 HTTPS Ingest 주소로 나가는 연결을 사용합니다. 대상 서버의 inbound
포트를 열 필요 없습니다. Sentra에서 같은 workspace의 heartbeat와 실제 수신 데이터를 확인하세요.
컨테이너 실행 성공만으로 인증·전송 성공을 판단하면 안 됩니다.
CPU/네트워크 사용률은 다음 수집 주기부터 생성됩니다.

읽기 위치는 쓰기 가능한 별도 `collector-state` Docker 볼륨에 보존합니다.
컨테이너를 재생성해도 이미 읽은 파일을 이어 읽습니다. 원본 파일은 수정하지 않습니다.
단, 현재 이미지는 전송 전에 읽기 위치를 저장하고 실패 데이터를 메모리 큐에만 보관하므로
전송 실패 중 재시작·큐 포화 때 유실 가능성이 있습니다. 내구성 큐와 rotation 처리는 후속 개선입니다.

```bash
sudo bash install.sh status
sudo bash install.sh logs
sudo bash install.sh stop
sudo bash install.sh update
sudo bash install.sh uninstall
```

uninstall은 컨테이너를 제거하지만 설정과 state 볼륨은 유지합니다.
이미지 교체는 `sudo env COLLECTOR_IMAGE=ghcr.io/seyun24/sentra-collector:<버전> bash install.sh update`로
수행합니다. 생성 설정에 이미지가 기록되어 status/stop에서 같은 설정을 사용합니다.
다음 install/update에서 다른 이미지를 원하면 다시 COLLECTOR_IMAGE를 지정하세요.

## 관리자: 이미지 게시

이미지는 비공개 Sentra 소스 저장소에서 빌드합니다.
현재 v0.1.0 재현에는 `patches/host-disk-root.patch`의 경로 설정 지원이 필요합니다.
기존 이미지 태그를 덮어쓰지 말고 코드 변경 시 새 버전을 게시하세요.

```bash
docker build --platform linux/amd64 -f collector/Dockerfile \
  -t ghcr.io/seyun24/sentra-collector:<새버전> .
docker push ghcr.io/seyun24/sentra-collector:<새버전>
```

토큰·설정 파일·개인키는 이미지에 넣지 않습니다. 공개 이미지 안의 Collector Python 코드는
다운로드한 사람이 볼 수 있습니다. GitHub Packages의 이미지 공개 여부는 저장소 공개와 별개입니다.
