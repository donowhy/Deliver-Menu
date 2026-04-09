# 변경사항

## 2026-04-10

- `app.py`
  - DB 웹훅 발송 대상 조회 시 잘못 참조하던 `wh.key`, `wh.type`를 실제 컬럼인 `webhook_url`, `name`으로 수정했습니다.
  - `active_yn=1` 인 웹훅만 발송 대상으로 사용하도록 정리했습니다.
  - `DATABASE_URL` 이 없을 때 `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` 또는 `MYSQL_ROOT_PASSWORD` 기반으로 SQLAlchemy MySQL 연결 문자열을 생성하도록 변경했습니다.
  - DB 조회/저장/삭제 실패 시 예외를 삼키지 않고 로그를 남기도록 수정했습니다.
  - 저장/삭제 실패 시 세션 롤백을 추가했습니다.
  - 화면에 전달하는 예약 발송 시간을 `schedule_time` 변수로 명시적으로 넘기도록 수정했습니다.

- `templates/index.html`
  - 화면 하단의 자동 발송 시간을 Flask `config` 대신 실제 전달된 `schedule_time` 값으로 표시하도록 수정했습니다.

- `docker-compose.yml`
  - MySQL 컨테이너 시작 시 초기 스키마를 자동 생성하도록 `./docker/mysql/init` 볼륨을 추가했습니다.
  - `web`, `scheduler` 컨테이너에 `MYSQL_HOST=db` 환경변수를 추가해 둘 다 동일한 MySQL 컨테이너를 바라보도록 정리했습니다.

- `docker/mysql/init/01_create_tb_webhook_config.sql`
  - 아래 스키마가 MySQL 초기화 시 자동 실행되도록 추가했습니다.

```sql
CREATE TABLE IF NOT EXISTS TB_WEBHOOK_CONFIG (
    id INT NOT NULL AUTO_INCREMENT,
    webhook_url VARCHAR(2000) NOT NULL,
    active_yn TINYINT NOT NULL DEFAULT 1,
    name VARCHAR(100) NOT NULL,
    PRIMARY KEY (id)
);
```
