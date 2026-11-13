# 로그인 계정으로 모의 카드 정지

프론트는 외부 OpenID Connect 서비스에서 로그인하고, 백엔드는 발급자가 서명한 액세스 토큰으로 카드 정지 요청의 소유자를 확인합니다. 로컬 검증은 JEV 키 없이 실행할 수 있고, 실제 카드에는 영향을 주지 않습니다.

## 로컬 Keycloak

1. [Keycloak 시작 가이드](https://www.keycloak.org/getting-started/getting-started-zip)에 따라 Keycloak과 해당 버전이 요구하는 Java를 준비합니다.
2. [kkbb-oidc-demo-realm.json](keycloak/kkbb-oidc-demo-realm.json)을 Keycloak의 `data/import/`에 복사하고 아래 명령으로 시작합니다.

   ```bash
   bin/kc.sh start-dev --http-host=127.0.0.1 --http-port=18088 \
     --hostname=http://localhost:18088 --import-realm
   ```

3. Keycloak의 관리자 화면에서 `kkbb-oidc-demo` realm을 선택하고 테스트 사용자와 비밀번호를 만듭니다. 샘플 realm에는 계정이나 비밀번호가 들어 있지 않습니다. 클라이언트 `kkbb-web`과 프론트 주소 `http://localhost:5173`이 미리 등록돼 있습니다.
4. 백엔드를 실행합니다.

   ```bash
   APP_ACTION_AUTH_ISSUER=http://localhost:18088/realms/kkbb-oidc-demo \
   APP_ACTION_AUTH_AUDIENCE=kkbb-actions \
   ./mvnw spring-boot:run -Dspring-boot.run.profiles=oidc-demo
   ```

5. [프론트 README](https://github.com/sunwoo030616/kkbb-ddook-ddak-front#로그인한-계정으로-카드-정지-확인)에 따라 로그인한 뒤 카드 정지를 확인합니다.

`oidc-demo`는 로컬에만 바인딩하며 고정 시나리오와 모의 카드 정지를 사용합니다. 발표용 익명 토큰 발급 경로는 열리지 않습니다. 이 프로필은 로컬 통합 검증에만 사용합니다.

## 팀 인증 서비스 연결

프론트의 `VITE_OIDC_ISSUER`와 백엔드의 `APP_ACTION_AUTH_ISSUER`에 같은 발급자 주소를 지정합니다. 프론트에는 공개 클라이언트 ID(`VITE_OIDC_CLIENT_ID`)만 넣고, 등록된 콜백과 로그아웃 주소는 각각 `/auth/callback`, `/auth/logout`입니다. 인증 서비스에는 프론트의 HTTPS 주소를 정확히 등록합니다. 공개 클라이언트는 Authorization Code + S256 PKCE를 사용합니다.

카드 정지용 JWT 액세스 토큰에는 사용자 식별자(`sub`), API 대상(`APP_ACTION_AUTH_AUDIENCE`), `actions:execute` 권한이 있어야 합니다. 인증 서비스에서 이 권한은 필요한 계정에만 부여합니다. ID 토큰과 감사 권한은 프론트에서 카드 정지 요청에 사용하지 않습니다. 일반 프로필에서 모의 카드 정지를 함께 검증할 때만 `APP_ACTION_DEMO_ENABLED=true`를 지정합니다. 실제 카드 시스템과 금융기관 본인확인은 별도 연동입니다.
