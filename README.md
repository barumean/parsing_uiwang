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

## 초기 세팅 (최초 1회)

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

---

## 이 저장소를 가져다 쓰는 방법

### 1단계 - 저장소 Fork
GitHub 저장소 우측 상단 **Fork** 버튼 클릭 → 본인 계정으로 복사

### 2단계 - Actions 활성화
Fork한 저장소에서 **Actions 탭** 클릭 → **"I understand my workflows, enable them"** 버튼 클릭
> Fork된 저장소는 기본적으로 Actions가 비활성화되어 있습니다.

### 3단계 - 텔레그램 봇 준비
위의 [텔레그램 봇 준비](#1-텔레그램-봇-준비) 항목 참고하여 본인의 봇 토큰과 Chat ID 준비

### 4단계 - Secrets 등록
Fork한 **본인 저장소**의 **Settings → Secrets and variables → Actions** 에서 등록
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### 5단계 - 첫 실행
Actions 탭 → **Check Uiwang Announcements** → **Run workflow** 클릭
- 첫 실행은 현재 공지 목록을 저장만 하고 알림은 보내지 않습니다.
- 이후 새 공지가 올라올 때마다 텔레그램으로 알림이 옵니다.
