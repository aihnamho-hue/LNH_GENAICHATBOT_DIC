# 대화 녹음 → Google Drive 저장 설정 가이드

세션이 끝나면 클라이언트가 **대화 녹음(내 목소리 + 마사마사 목소리 믹스 1개 파일)** 과
**대화 기록(txt)** 을 서버로 업로드하고, 서버가 이를 운영자의 Google Drive에 저장한다.

Render 디스크는 ephemeral(재배포/재시작 시 삭제)이라 외부 저장소가 필수다.
환경변수를 설정하지 않으면 서버의 `recordings/` 폴더에 임시 저장된다(재배포 시 사라짐).

> **왜 서비스 계정이 아니라 OAuth인가?**
> Google이 서비스 계정의 My Drive 파일 소유를 막아서(저장 용량 0),
> 서비스 계정으로 업로드하면 `storageQuotaExceeded` 에러가 난다.
> 개인 Gmail 계정은 공유 드라이브도 못 만들기 때문에,
> 본인 계정 OAuth(리프레시 토큰) 방식이 유일한 정석 루트다.

## 1. GCP 프로젝트 준비 (약 5분)

1. https://console.cloud.google.com → 새 프로젝트 생성 (이름 아무거나, 예: `masamasa`)
2. **API 및 서비스 → 라이브러리** → "Google Drive API" 검색 → **사용 설정**
3. **API 및 서비스 → OAuth 동의 화면**
   - User Type: **외부(External)** → 앱 이름/이메일 입력 → 저장
   - **⚠️ 중요: "앱 게시(Publish App)" 버튼을 눌러 프로덕션 상태로 전환**
     - 테스트 모드로 두면 리프레시 토큰이 **7일마다 만료**된다
     - `drive.file` 스코프는 민감하지 않은 권한이라 심사 없이 게시 가능
4. **API 및 서비스 → 사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**
   - 애플리케이션 유형: **데스크톱 앱**
   - 생성된 **클라이언트 ID**와 **클라이언트 보안 비밀번호(Secret)** 를 복사해 둔다

## 2. 리프레시 토큰 발급 (내 PC에서 1번)

```bash
pip install google-auth-oauthlib
python get_gdrive_token.py
```

ID/Secret을 붙여넣으면 브라우저가 열린다 → 구글 로그인 → 동의 →
터미널에 환경변수 3개가 출력된다.

## 3. Render 환경변수 등록

Render 대시보드 → masamasa-chatbot → **Environment** 에 추가:

| 키 | 값 |
|---|---|
| `GDRIVE_CLIENT_ID` | 1단계에서 만든 클라이언트 ID |
| `GDRIVE_CLIENT_SECRET` | 클라이언트 Secret |
| `GDRIVE_REFRESH_TOKEN` | 2단계 스크립트가 출력한 토큰 |
| `GDRIVE_FOLDER_NAME` | (선택) 저장 폴더 이름. 기본값 `masamasa-recordings` |

저장하면 자동 재배포된다.

## 4. 동작 확인

1. 사이트 접속 → 녹음 동의 → 대화 → 종료
2. 화면 하단에 "✅ 대화 녹음이 저장되었어요" 표시 확인
3. 내 Google Drive에 `masamasa-recordings` 폴더가 자동 생성되고
   그 안에 `마사마사대화_YYYYMMDD_HHMMSS_D##_P##.webm`(또는 .m4a) + `.txt`가 쌓인다

## 참고

- 녹음 파일은 opus 48kbps 압축이라 10분 대화 ≈ 3~4MB. 15GB 무료 용량으로 충분
- 학습자에게는 대화 시작 전 **녹음 동의 모달**이 1회 표시되고, 동의해야 대화가 시작된다

## (별개) Render 리전 이전 — 싱가포르

`render.yaml`에 `region: singapore`를 추가해 두었지만, **이미 만들어진 서비스는
리전이 바뀌지 않는다.** 옮기려면: 대시보드에서 기존 서비스 삭제 → 저장소를
Blueprint로 다시 연결(New → Blueprint) → 환경변수 재입력. 무료 플랜 기준 5분 작업이고
한국↔서버 왕복 지연이 크게 줄어든다.
