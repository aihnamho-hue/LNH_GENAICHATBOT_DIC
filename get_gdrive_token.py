"""
Google Drive 리프레시 토큰 발급 스크립트 — 내 PC에서 딱 1번만 실행

준비물: GCP OAuth 클라이언트 ID/Secret (발급 방법은 GDRIVE_SETUP.md 참고)

실행:
  pip install google-auth-oauthlib
  python get_gdrive_token.py

브라우저가 열리면 구글 계정으로 로그인·동의하면 끝.
출력된 3개 값을 Render 환경변수에 등록하면 된다.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]  # 이 앱이 만든 파일만 접근 (최소 권한)

client_id = input("OAuth 클라이언트 ID: ").strip()
client_secret = input("OAuth 클라이언트 Secret: ").strip()

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    },
    scopes=SCOPES,
)

# access_type=offline + prompt=consent 조합이어야 리프레시 토큰이 반드시 발급됨
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

print()
print("=" * 60)
print("아래 3개를 Render 환경변수로 등록하세요")
print("=" * 60)
print(f"GDRIVE_CLIENT_ID={client_id}")
print(f"GDRIVE_CLIENT_SECRET={client_secret}")
print(f"GDRIVE_REFRESH_TOKEN={creds.refresh_token}")
print("=" * 60)
