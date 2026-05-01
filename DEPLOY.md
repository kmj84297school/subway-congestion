# 배포 가이드 (Render.com)

발표 며칠 전에 따라하면 인터넷에서 누구나 접속 가능한 형태로 배포된다.
**예상 소요 시간: 처음 시도 시 20~30분, 익숙해지면 5분.**

---

## 0. 사전 준비물

- GitHub 계정 ✓ (있다고 하셨음)
- git 명령어 사용 가능 ✓
- 신용카드 **불필요** (Render 무료 티어)

---

## 1. GitHub 저장소 만들기

GitHub 웹사이트에서 새 저장소 생성:
- 이름: `subway-congestion` (또는 원하는 이름)
- Public / Private 어느 쪽이든 OK (Render 무료 티어는 Public/Private 모두 지원)
- README, .gitignore, license는 **만들지 않기** (이미 로컬에 있음)

저장소 URL을 복사해둔다 (예: `https://github.com/USERNAME/subway-congestion.git`).

---

## 2. 로컬에서 git 초기화 + 첫 푸시

프로젝트 루트(`subway_project/`)에서:

```bash
# git 초기화
git init
git branch -M main

# 모든 파일 추가 (.gitignore가 자동으로 불필요한 것 제외)
git add .
git commit -m "Initial commit: 지하철 혼잡 예측 모델"

# 원격 저장소 연결
git remote add origin https://github.com/USERNAME/subway-congestion.git

# 푸시
git push -u origin main
```

**[확인]** GitHub 웹페이지를 새로고침해서 파일들이 올라갔는지 확인.

---

## 3. Render 가입

1. https://render.com 접속 → "Get Started for Free"
2. **"GitHub로 가입"** 선택 (가장 간단함)
3. GitHub 권한 요청 → **Authorize** 승인
4. Render 대시보드 진입

**카드 등록 안 해도 됨**. 무료 티어는 카드 없이 바로 사용 가능.

---

## 4. Blueprint으로 배포 (가장 쉬운 방법)

이 프로젝트에 `render.yaml` 이 있어 Blueprint으로 자동 배포가 가능하다.

1. Render 대시보드 → 우상단 **"New +"** → **"Blueprint"**
2. GitHub 저장소 목록에서 `subway-congestion` 선택
3. Render가 `render.yaml`을 읽고 설정을 자동으로 보여줌 → 그대로 **"Apply"**
4. 약 3~5분 기다리면 빌드 + 배포 완료

빌드 로그 보는 법:
- 대시보드 → 서비스 클릭 → **"Logs"** 탭
- "Your service is live" 메시지가 보이면 성공

---

## 5. 배포 확인

서비스 페이지 상단의 **URL** (예: `https://subway-congestion.onrender.com`)을 클릭하면 사이트가 열린다.

**첫 접속이 느린 이유:**
무료 티어는 15분 미사용 시 슬립 상태가 된다. 슬립에서 깨어나는 데 약 30초 걸림. 두 번째 요청부터는 정상 속도.

**[확인]** 메인 페이지에서 강남 / 평일 / 18시 입력 후 "분석 실행" → 결과가 정상적으로 나오면 성공.

---

## 6. 발표 직전 체크리스트

발표 5~10분 전에:

1. **사이트를 한 번 접속해서 깨우기** (슬립 상태 해제)
2. **분석 한 번 실행** (모델 캐시 워밍)
3. URL 복사해두기 (QR 코드로 만들면 친구들이 폰으로 바로 접속 가능 — qr-code-generator.com 등 사용)

---

## 7. 코드 수정 후 재배포

수정 후 다음 명령만 실행:

```bash
git add .
git commit -m "수정 내용 요약"
git push
```

Render가 push를 감지해서 **자동으로 재배포**한다 (3~5분 소요).

---

## 8. 자주 발생하는 문제

### 8-1. 빌드 실패: "Could not find requirements.txt"
- 원인: 푸시할 때 `requirements.txt`가 빠짐
- 해결: 프로젝트 루트에 있는지 확인 → `git add requirements.txt && git commit && git push`

### 8-2. 한글이 □□□ 로 표시됨
- 원인: Render의 리눅스 환경에 한글 폰트가 없는 경우
- 해결: 본 프로젝트는 `Noto Sans CJK` 가 기본 포함된 빌드팩을 사용하므로 정상 작동해야 함. 만약 깨지면 빌드 명령에 폰트 설치 추가:
  ```yaml
  buildCommand: apt-get update && apt-get install -y fonts-noto-cjk && pip install -r requirements.txt
  ```
  단, 무료 티어에서 apt 사용이 제한될 수 있음. 이 경우 `fonts-noto-cjk` 대신 NanumGothic.ttf 파일을 저장소에 직접 포함하는 것이 가장 안전.

### 8-3. "Application failed to respond"
- 원인: 보통 시작 명령(`startCommand`)에서 포트 처리 누락
- 해결: `render.yaml`의 `startCommand`에 `--port $PORT`가 있는지 확인

### 8-4. 슬립 후 응답이 너무 느림
- 무료 티어의 한계. 발표 5분 전에 한 번 깨워두는 것으로 해결.
- 발표 도중 갑자기 느려지면 안 되므로, 발표 시작 직전 한 번 더 새로고침 권장.

---

## 9. 배포 후 URL 공유

배포가 끝나면 받게 되는 URL은:
- `https://subway-congestion-xxxx.onrender.com` 형태

이 URL을:
- QR 코드로 만들기 → 발표 슬라이드에 삽입
- 카톡/디스코드로 친구들에게 공유 → 본인 폰에서 직접 사용해보게

**중요**: Render 무료 티어는 한 달 750시간까지 무료. 한 서비스만 배포하면 항상 무료(상시 750시간 < 한 달 720시간).

---

## 10. 배포 비용

| 단계 | 비용 |
|---|---|
| GitHub 저장소 (Public 또는 Private) | 무료 |
| Render 무료 티어 | 무료 (카드 등록 불필요) |
| 도메인 (`*.onrender.com` 자동) | 무료 |
| **합계** | **0원** |

원하면 나중에 본인 도메인(예: `subway.이름.com`)을 연결할 수도 있다. 도메인 구입비 약 1.5만원/년 + Render 설정 변경.
