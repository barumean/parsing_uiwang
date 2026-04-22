# 의왕시 공지사항 알리미

의왕시 홈페이지 공지사항을 자동으로 확인하고, 새 글이 올라오면 텔레그램으로 알려주는 프로그램입니다.

## 작동 방식

- GitHub Actions가 **평일 오전 11시**에 자동으로 실행됩니다.
- [의왕시 공지사항 페이지](https://www.uiwang.go.kr/UWKORINFO0101)를 크롤링합니다.
- 이전 실행 때와 비교해서 새 글이 있으면 텔레그램 메시지를 보냅니다.
- 확인한 공지 목록은 `seen_announcements.json`에 저장됩니다.

## 구조

```
├── checker.py                              # 크롤링 및 알림 전송 스크립트
├── requirements.txt                        # Python 패키지 목록
├── seen_announcements.json                 # 마지막으로 확인한 공지 목록 (자동 관리)
└── .github/workflows/check_announcements.yml  # GitHub Actions 스케줄 설정
```

## 초기 세팅

### 1. 텔레그램 봇 준비
1. Telegram에서 `@BotFather`에게 `/newbot` 으로 봇 생성 후 토큰 발급
2. 봇에게 `/start` 전송
3. 아래 URL에서 `chat.id` 값 확인
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

### 2. GitHub Secrets 등록
저장소 **Settings → Secrets and variables → Actions** 에서 아래 두 값 등록

| 이름 | 값 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather에서 발급받은 토큰 |
| `TELEGRAM_CHAT_ID` | 위에서 확인한 chat id |

### 3. 동작 확인
Actions 탭 → **Check Uiwang Announcements** → **Run workflow** 로 수동 실행 가능
