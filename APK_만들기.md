# 호아랑 APK 만들기 — 30분이면 끝납니다

코딩 없이, 브라우저에서 다 됩니다. 순서대로만 따라오세요.

**지금 서버는 이미 준비돼 있습니다(v51).** APK 파일을 `static/hoarang.apk`에 넣고 배포하면, 안드로이드 학생이 사이트를 열었을 때 **자동으로 「앱 파일 받기」 버튼**이 나옵니다. 아이폰 학생에게는 지금처럼 '홈 화면에 추가' 안내가 나갑니다.

---

## 1단계 — PWABuilder에서 패키지 만들기 (10분)

1. https://www.pwabuilder.com 접속
2. 주소창에 `https://korean-dic.onrender.com` 입력 → **Start**
3. 점수 화면이 나오면 → **Package for stores**
4. **Android** 칸에서 **Generate Package**
5. 설정을 이렇게 맞춥니다

| 항목 | 값 | 왜 |
|---|---|---|
| Package ID | `com.hoarang.app` | 앱의 고유 이름. **한 번 정하면 절대 못 바꿉니다** |
| App name | `호아랑` | 폰에 표시될 이름 |
| Launcher name | `호아랑` | 아이콘 밑 글자 (12자 이내) |
| App version | `1.0.0` | |
| Signing key | **Create new** | 처음이니까 새로 만듭니다 |
| Include source code | 체크 | 나중에 손볼 때 필요 |

> **Package ID에 한글(`호아랑`)은 못 씁니다.** 안드로이드가 영문 소문자·숫자·점(`.`)만 받고, 각 마디는 글자로 시작해야 합니다. 한글을 넣으면 빌드가 실패합니다.
> 대신 **학생 눈에는 이 값이 어디에도 보이지 않습니다.** 폰에 뜨는 이름은 바로 아래 App name(`호아랑`)입니다. Package ID는 안드로이드가 앱을 구분하는 내부 번호라고 보시면 됩니다.
> 서버 기본값도 `com.hoarang.app`으로 맞춰 두었으니 그대로 쓰시면 됩니다. (예전 `com.masamasa.chatbot`은 마사마사 시절 이름이라 버렸습니다)

6. **Download** → zip 파일이 받아집니다

## 2단계 — ★ 키스토어를 잃어버리지 마세요

zip 안에 **`signing.keystore`** 와 **비밀번호가 적힌 파일**이 들어 있습니다.

> **이걸 잃어버리면 앱을 영원히 업데이트할 수 없습니다.**
> 같은 Package ID로 새 키를 써서 만든 APK는 "이미 설치된 앱과 서명이 다르다"며 설치가 거부됩니다. 학생들이 앱을 지우고 다시 깔아야 합니다.

지금 바로 `C:\SynologyDrive\08. 코딩\음성 대화형 챗봇\_keystore\` 같은 폴더를 만들어 넣어 두세요. **깃헙에는 절대 올리지 마세요.**

## 3단계 — assetlinks 등록 (주소창 없애기)

이걸 안 하면 앱 위쪽에 주소가 잠깐 뜹니다.

zip 안에 **`assetlinks.json`** 이 들어 있습니다. 그 파일을 그대로 `static/assetlinks.json`에 넣고 배포하세요. 서버가 알아서 `/.well-known/assetlinks.json` 주소로 내보냅니다.

> 파일이 안 보이면, zip 안 `signing-key-info.txt`의 **SHA-256 fingerprint** 값을 Render 환경변수 `TWA_FINGERPRINT`에 넣어도 됩니다. (`TWA_PACKAGE`는 기본값이 `com.hoarang.app`)

**확인**: 배포 후 `https://korean-dic.onrender.com/.well-known/assetlinks.json`을 열어 JSON이 나오면 성공입니다.

## 4단계 — APK를 서버에 올리기

zip 안에 `app-release-signed.apk`(또는 `.apk`)가 있습니다.

1. 이름을 **`hoarang.apk`** 로 바꿉니다
2. `static/hoarang.apk` 에 넣습니다
3. 깃헙에 올리고 배포

**확인**: `https://korean-dic.onrender.com/app-info` 를 열어 `"apk": "/download/hoarang.apk"` 가 나오면 성공입니다.

---

## 학생에게는 이렇게 안내하세요

> 안드로이드는 **주소만 보내면 됩니다.** 열면 알아서 「앱 파일 받기」가 뜹니다.

```
한국어 연습 앱이에요 🐯
아래 주소를 눌러서 안내대로 설치해 주세요.
https://korean-dic.onrender.com
```

### 수업 시간에 같이 하실 것 (3분)

안드로이드 학생은 설치 도중 **"출처를 알 수 없는 앱"** 경고를 한 번 만납니다.

> 1. 「앱 파일 받기」를 누른다
> 2. 아래로 알림이 뜨면 **「열기」**
> 3. "이 출처의 앱 설치 허용" 화면이 뜨면 **스위치를 켠다** → 뒤로가기
> 4. **「설치」** → 끝

이 화면은 안드로이드가 강제하는 것이라 없앨 수 없습니다. **한 명씩이 아니라 다 같이 한 번에 하시면 3분이면 끝납니다.**

아이폰 학생은 APK를 쓸 수 없으므로, 관문이 자동으로 **공유 ⬆︎ → '홈 화면에 추가'** 안내를 띄웁니다.

---

## 알아 두실 것

**내용 수정은 APK를 다시 안 만들어도 됩니다.** APK는 사이트를 감싸는 껍데기라, 깃헙에 올려 배포하면 학생 앱에 바로 반영됩니다. APK를 다시 만들어야 하는 건 **아이콘·앱 이름·Package ID를 바꿀 때뿐**입니다.

**알림은 그대로 작동합니다.** 다만 앱을 처음 열 때 안드로이드가 알림 권한을 다시 물어봅니다(안드로이드 13+). 지금 만들어 둔 권유 화면이 그 역할을 합니다.

**나중에 플레이스토어에 올리고 싶다면** zip 안의 `.aab` 파일을 쓰시면 됩니다. 같은 키스토어를 그대로 쓰면 이어집니다. 등록비 $25(1회), 개인정보처리방침 페이지와 데이터 안전 양식(마이크·음성 수집)이 필요합니다.

---

## 막히면

- **"설치가 계속 실패해요"** → 이미 같은 앱이 다른 서명으로 깔려 있는 경우입니다. 지우고 다시 설치
- **앱 위에 주소가 보여요** → 3단계 assetlinks가 안 된 것. `/.well-known/assetlinks.json` 확인
- **버튼이 안 나와요** → `/app-info`를 열어 `apk` 값이 비어 있는지 확인

zip 파일을 저한테 주시면 안에 뭐가 들었는지 확인하고 배치까지 해 드리겠습니다.

---

Sources: [PWABuilder Android (Bubblewrap/TWA)](https://github.com/pwa-builder/pwabuilder-google-play) · [WebAPKs on Android — web.dev](https://web.dev/articles/webapks)
