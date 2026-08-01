# 네이티브 앱(iOS/Android) 빌드 가이드

이 폴더는 배포된 웹앱(`main.py`)을 그대로 감싸서 iOS/Android 앱으로 만드는 [Capacitor](https://capacitorjs.com/) 프로젝트입니다. 실제 빌드는 Xcode(iOS, Mac 전용) 또는 Android Studio(Android)가 설치된 본인 컴퓨터에서 진행해야 합니다.

## 사전 준비

1. 서버가 먼저 공개 URL로 배포되어 있어야 합니다 (`../README.md`의 Render 배포 단계 참고)
2. `capacitor.config.json`의 `server.url` 값을 배포된 실제 주소로 수정
3. Node.js 설치 (18 이상 권장)
4. iOS 빌드: Mac + Xcode + Apple Developer Program 계정 (연 $99)
5. Android 빌드: Android Studio + Google Play Console 계정 (1회 $25)

## 실행 순서

```bash
cd capacitor-app
npm install

# 플랫폼 추가 (최초 1회씩)
npx cap add ios
npx cap add android

# 배포 서버 주소가 바뀔 때마다
npx cap sync

# 각 IDE로 열어서 빌드/실행
npx cap open ios       # Xcode 열림
npx cap open android   # Android Studio 열림
```

## 마이크 권한 설정 (필수)

이 앱은 마이크를 사용하므로, 플랫폼 추가 후 아래 설정을 반드시 추가해야 합니다.

**iOS** (`ios/App/App/Info.plist`):
```xml
<key>NSMicrophoneUsageDescription</key>
<string>호아랑와 음성으로 대화하기 위해 마이크 접근이 필요합니다.</string>
```

**Android** (`android/app/src/main/AndroidManifest.xml`):
```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.INTERNET" />
```

## 볼륨 버튼이 '통화 음량'을 조절하는 문제 해결 (Android · 필수)

마이크를 쓰는 WebView 앱은 Android가 오디오를 '통신(통화)' 모드로 잡아서, 볼륨 버튼이 **미디어 음량이 아니라 통화 음량**을 조절하는 문제가 생깁니다. 아래 한 줄로 볼륨 버튼이 항상 **미디어(음악) 음량**을 조절하게 고정합니다.

`android/app/src/main/java/.../MainActivity.java` (또는 `.kt`)의 `onCreate`에 추가:

```java
import android.media.AudioManager;
// ...
@Override
public void onCreate(Bundle savedInstanceState) {
    super.onCreate(savedInstanceState);
    // 볼륨 버튼을 항상 미디어(음악) 스트림에 고정 → 통화 음량이 아닌 미디어 음량 조절
    setVolumeControlStream(AudioManager.STREAM_MUSIC);
}
```

Kotlin이라면:

```kotlin
import android.media.AudioManager
// ...
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    volumeControlStream = AudioManager.STREAM_MUSIC
}
```

> 순수 웹(PWA)에서는 브라우저가 오디오 스트림 종류를 강제할 API가 없어 이 문제를 코드로 완전히 없앨 수 없습니다. 가능하면 **이어폰 사용**을 권장(앱 내 안내 팝업 참고)하면 증상이 줄어듭니다. 네이티브 앱에서는 위 설정이 확실한 해결책입니다.

## 스토어 등록

- iOS: App Store Connect에서 앱 등록 → Xcode에서 Archive → 업로드 → 심사 제출 (보통 1~3일 소요)
- Android: Google Play Console에서 앱 등록 → Android Studio에서 서명된 AAB 빌드 → 업로드 → 심사 제출 (보통 몇 시간~며칠)

두 스토어 모두 개인정보처리방침 URL, 앱 아이콘, 스크린샷 등이 필요합니다. 이 단계는 계정이 준비되면 같이 진행하면 돼.
