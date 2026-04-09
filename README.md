# Deliver Menu

식단 정보를 조회해서 등록된 웹훅으로 발송하는 Flask 애플리케이션입니다.

## 구성

- `web`: 웹 관리 화면
- `scheduler`: 매일 지정된 시간에 자동 발송
- `db`: MySQL 8.0

## 필수 환경변수

`.env` 파일을 프로젝트 루트에 두고 아래 값을 설정합니다.

```env
MYSQL_ROOT_PASSWORD=change-me
MYSQL_DATABASE=menu_deliver
TZ=Asia/Seoul
SECRET_KEY=change-this-to-a-long-random-string
SCHEDULE_TIME=07:50
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-this-password
```

선택 환경변수:

```env
WEBHOOK_URLS=https://example1,https://example2
MYSQL_HOST=db
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=change-me
```

## 실행

```bash
docker compose up -d --build
```

웹 관리 화면:

- `http://<EC2_PUBLIC_IP>/login`

## 로그인 보호

- 관리 화면, 등록, 삭제, 테스트 발송은 로그인 후에만 접근할 수 있습니다.
- 로그인 계정은 `ADMIN_USERNAME`, `ADMIN_PASSWORD` 환경변수로 제어합니다.
- `ADMIN_PASSWORD`를 비워두지 않는 것을 권장합니다.

## DB 초기화

MySQL 시작 시 아래 테이블이 자동 생성됩니다.

```sql
CREATE TABLE IF NOT EXISTS TB_WEBHOOK_CONFIG (
    id INT NOT NULL AUTO_INCREMENT,
    webhook_url VARCHAR(2000) NOT NULL,
    active_yn TINYINT NOT NULL DEFAULT 1,
    name VARCHAR(100) NOT NULL,
    PRIMARY KEY (id)
);
```

초기화 스크립트 위치:

- `docker/mysql/init/01_create_tb_webhook_config.sql`

## 보안 메모

- 현재 로그인 보호는 앱 레벨 보호입니다.
- 회사 공인 IP를 확인한 뒤 EC2 보안그룹에서 해당 IP만 허용하는 것을 권장합니다.
- 도메인과 인증서가 없으면 HTTPS 없이 운영되므로, 민감한 비밀번호는 재사용하지 않는 편이 맞습니다.
